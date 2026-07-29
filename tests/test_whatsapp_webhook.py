from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.whatsapp import router
from app.core.config import settings


@dataclass
class FakeChatService:
    response: Any = "Thanks!"
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def chat(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


@dataclass
class FakeOutboundService:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def send_text_message(self, recipient_phone: str, text: str) -> dict[str, Any]:
        payload = {"recipient_phone": recipient_phone, "text": text}
        self.calls.append(payload)
        return {"status": "ok"}


def build_app(chat_service: FakeChatService, outbound_service: FakeOutboundService | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.chat_service = chat_service
    if outbound_service is not None:
        app.state.whatsapp_outbound_service = outbound_service
    return app


def meta_text_payload(message_id: str = "wamid.1", sender: str = "15551234567", body: str = "Hello") -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry-1",
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": sender,
                                    "id": message_id,
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {"body": body},
                                }
                            ]
                        }
                    }
                ],
            }
        ],
    }


def meta_status_payload() -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry-1",
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": "wamid.status",
                                    "status": "delivered",
                                }
                            ]
                        }
                    }
                ],
            }
        ],
    }


@pytest.fixture(autouse=True)
def whatsapp_verify_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "test-verify-token", raising=False)


def test_get_webhook_verification_success() -> None:
    app = build_app(FakeChatService())
    with TestClient(app) as client:
        response = client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token",
                "hub.challenge": "12345",
            },
        )

    assert response.status_code == 200
    assert response.text == "12345"


def test_get_webhook_verification_failure() -> None:
    app = build_app(FakeChatService())
    with TestClient(app) as client:
        response = client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "12345",
            },
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Verification failed"}


def test_valid_incoming_text_message_routes_to_chat_and_outbound() -> None:
    chat_service = FakeChatService(response={"response": "Order received"})
    outbound_service = FakeOutboundService()
    app = build_app(chat_service, outbound_service)

    with TestClient(app) as client:
        response = client.post("/webhooks/whatsapp", json=meta_text_payload())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert chat_service.calls == [
        {
            "message": "Hello",
            "conversation_id": "15551234567",
            "customer_phone": "15551234567",
            "message_id": "wamid.1",
        }
    ]
    assert outbound_service.calls == [{"recipient_phone": "15551234567", "text": "Order received"}]


def test_phone_and_message_id_propagation_for_idempotency() -> None:
    chat_service = FakeChatService(response="Thanks!")
    outbound_service = FakeOutboundService()
    app = build_app(chat_service, outbound_service)

    with TestClient(app) as client:
        first = client.post("/webhooks/whatsapp", json=meta_text_payload(message_id="wamid.2", sender="15550001111"))
        second = client.post("/webhooks/whatsapp", json=meta_text_payload(message_id="wamid.2", sender="15550001111"))

    assert first.status_code == 200
    assert second.status_code == 200
    assert chat_service.calls[0]["customer_phone"] == "15550001111"
    assert chat_service.calls[0]["conversation_id"] == "15550001111"
    assert len(chat_service.calls) == 1
    assert len(outbound_service.calls) == 1


def test_duplicate_webhook_event_does_not_duplicate_cart_updates() -> None:
    chat_service = FakeChatService(response="Thanks!")
    outbound_service = FakeOutboundService()
    app = build_app(chat_service, outbound_service)

    with TestClient(app) as client:
        client.post("/webhooks/whatsapp", json=meta_text_payload(message_id="wamid.dup"))
        client.post("/webhooks/whatsapp", json=meta_text_payload(message_id="wamid.dup"))

    assert len(chat_service.calls) == 1
    assert len(outbound_service.calls) == 1


def test_malformed_payload_is_ignored() -> None:
    chat_service = FakeChatService()
    outbound_service = FakeOutboundService()
    app = build_app(chat_service, outbound_service)

    with TestClient(app) as client:
        response = client.post("/webhooks/whatsapp", json={"unexpected": True})

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert chat_service.calls == []
    assert outbound_service.calls == []


def test_status_only_event_is_ignored() -> None:
    chat_service = FakeChatService()
    outbound_service = FakeOutboundService()
    app = build_app(chat_service, outbound_service)

    with TestClient(app) as client:
        response = client.post("/webhooks/whatsapp", json=meta_status_payload())

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert chat_service.calls == []
    assert outbound_service.calls == []


def test_unsupported_message_type_is_ignored() -> None:
    chat_service = FakeChatService()
    outbound_service = FakeOutboundService()
    app = build_app(chat_service, outbound_service)
    payload = meta_text_payload()
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
    payload["entry"][0]["changes"][0]["value"]["messages"][0].pop("text", None)

    with TestClient(app) as client:
        response = client.post("/webhooks/whatsapp", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert chat_service.calls == []
    assert outbound_service.calls == []


def test_workflow_response_is_passed_to_outbound_client() -> None:
    chat_service = FakeChatService(response={"response": "Here is your cart"})
    outbound_service = FakeOutboundService()
    app = build_app(chat_service, outbound_service)

    with TestClient(app) as client:
        client.post("/webhooks/whatsapp", json=meta_text_payload())

    assert outbound_service.calls[-1]["text"] == "Here is your cart"


def test_invalid_signature_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    chat_service = FakeChatService()
    outbound_service = FakeOutboundService()
    app = build_app(chat_service, outbound_service)
    app.state.whatsapp_webhook_service = app.state.whatsapp_webhook_service if hasattr(app.state, "whatsapp_webhook_service") else None
    app.state.whatsapp_webhook_service = None

    from app.services.whatsapp_transport import WhatsAppWebhookService

    app.state.whatsapp_webhook_service = WhatsAppWebhookService(
        chat_service=chat_service,
        outbound_service=outbound_service,
        signature_secret="secret",
        verify_token="test-verify-token",
    )

    with TestClient(app) as client:
        response = client.post(
            "/webhooks/whatsapp",
            json=meta_text_payload(),
            headers={"X-Hub-Signature-256": "sha256=invalid"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "invalid_signature"}

