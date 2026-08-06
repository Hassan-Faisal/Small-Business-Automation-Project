from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.meta import router
from app.core.config import settings
from app.services.meta_message_processing_service import MetaMessageProcessingService
from app.services.whatsapp_outbound_provider import MetaWhatsAppOutboundProvider


class FakeChat:
    def __init__(self, response: Any = "Reply from ordering workflow", error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeOutbound:
    def __init__(self, result: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.result = result or {"status": "ok", "data": {"messages": [{"id": "wamid.reply"}]}}
        self.error = error
        self.calls: list[dict[str, str]] = []

    async def send_text_message(self, recipient_phone: str, text: str) -> dict[str, Any]:
        self.calls.append({"recipient_phone": recipient_phone, "text": text})
        if self.error:
            raise self.error
        return self.result


def payload(*, message_id: str = "wamid.inbound", sender: str = "923244248414", body: str = "today menu", message_type: str = "text") -> dict[str, Any]:
    message: dict[str, Any] = {"from": sender, "id": message_id, "timestamp": "1710000000", "type": message_type}
    if message_type == "text":
        message["text"] = {"body": body}
    return {"object": "whatsapp_business_account", "entry": [{"id": "waba-1", "changes": [{"field": "messages", "value": {"metadata": {"phone_number_id": "phone-1"}, "contacts": [{"wa_id": sender}], "messages": [message]}}]}]}


def signed(value: dict[str, Any], secret: str = "app-secret") -> tuple[bytes, dict[str, str]]:
    body = json.dumps(value).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, {"X-Hub-Signature-256": f"sha256={signature}"}


def build_app(chat: FakeChat, provider: MetaWhatsAppOutboundProvider) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.chat_service = chat
    app.state.meta_message_processing_service = MetaMessageProcessingService(chat, provider)
    return app


@pytest.fixture(autouse=True)
def settings_for_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "META_APP_SECRET", "app-secret")
    monkeypatch.setattr(settings, "META_SIGNATURE_VERIFICATION_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "access-secret")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "phone-1")
    monkeypatch.setattr(settings, "WHATSAPP_API_VERSION", "v21.0")
    monkeypatch.setattr(settings, "WHATSAPP_OUTBOUND_PROVIDER", "meta")


def provider(outbound: FakeOutbound) -> MetaWhatsAppOutboundProvider:
    return MetaWhatsAppOutboundProvider(outbound_service=outbound, send_runner=lambda awaitable: asyncio.run(awaitable))


def test_valid_text_invokes_chat_and_meta_reply_with_twilio_convention() -> None:
    chat = FakeChat(response="Here is today's menu")
    outbound = FakeOutbound()
    body, headers = signed(payload())
    with TestClient(build_app(chat, provider(outbound))) as client:
        response = client.post("/webhooks/meta", content=body, headers=headers)
    assert response.status_code == 200
    assert chat.calls == [{"message": "today menu", "conversation_id": "whatsapp:+923244248414", "customer_phone": "whatsapp:+923244248414", "message_id": "wamid.inbound"}]
    assert outbound.calls == [{"recipient_phone": "923244248414", "text": "Here is today's menu"}]


def test_multiple_entries_and_changes_process_all_messages() -> None:
    chat = FakeChat(response="Reply")
    outbound = FakeOutbound()
    value = payload(message_id="wamid.1")
    second = payload(message_id="wamid.2", body="view cart")
    value["entry"].extend(second["entry"])
    body, headers = signed(value)
    with TestClient(build_app(chat, provider(outbound))) as client:
        response = client.post("/webhooks/meta", content=body, headers=headers)
    assert response.status_code == 200
    assert [call["message_id"] for call in chat.calls] == ["wamid.1", "wamid.2"]
    assert len(outbound.calls) == 2


def test_dashboard_style_payload_without_field_remains_compatible() -> None:
    chat = FakeChat(response="Reply")
    outbound = FakeOutbound()
    value = payload()
    del value["entry"][0]["changes"][0]["field"]
    body, headers = signed(value)
    with TestClient(build_app(chat, provider(outbound))) as client:
        response = client.post("/webhooks/meta", content=body, headers=headers)
    assert response.status_code == 200
    assert len(chat.calls) == 1


def test_chat_failure_does_not_call_outbound() -> None:
    chat = FakeChat(error=RuntimeError("workflow failure"))
    outbound = FakeOutbound()
    body, headers = signed(payload())
    with TestClient(build_app(chat, provider(outbound))) as client:
        response = client.post("/webhooks/meta", content=body, headers=headers)
    assert response.status_code == 200
    assert outbound.calls == []


def test_outbound_failure_does_not_crash_webhook() -> None:
    chat = FakeChat(response="Reply")
    outbound = FakeOutbound(error=RuntimeError("Meta unavailable"))
    body, headers = signed(payload())
    with TestClient(build_app(chat, provider(outbound))) as client:
        response = client.post("/webhooks/meta", content=body, headers=headers)
    assert response.status_code == 200
    assert len(chat.calls) == 1
    assert len(outbound.calls) == 1


def test_duplicate_does_not_invoke_chat_or_outbound_twice() -> None:
    chat = FakeChat(response="Reply")
    outbound = FakeOutbound()
    body, headers = signed(payload(message_id="wamid.same"))
    with TestClient(build_app(chat, provider(outbound))) as client:
        first = client.post("/webhooks/meta", content=body, headers=headers)
        second = client.post("/webhooks/meta", content=body, headers=headers)
    assert first.json() == {"status": "received"}
    assert second.json() == {"status": "duplicate"}
    assert len(chat.calls) == 1
    assert len(outbound.calls) == 1


def test_no_automatic_twilio_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WHATSAPP_OUTBOUND_PROVIDER", "twilio")
    chat = FakeChat(response="Should not run")
    outbound = FakeOutbound()
    body, headers = signed(payload())
    with TestClient(build_app(chat, provider(outbound))) as client:
        response = client.post("/webhooks/meta", content=body, headers=headers)
    assert response.status_code == 200
    assert chat.calls == []
    assert outbound.calls == []
