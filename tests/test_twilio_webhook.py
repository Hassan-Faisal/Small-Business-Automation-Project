from __future__ import annotations

import base64
import hashlib
import hmac
import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any
from xml.sax.saxutils import escape

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.twilio import router as twilio_router
from app.core.config import settings
from app.services.whatsapp_transport import WhatsAppWebhookService


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
    app.include_router(twilio_router)
    app.state.chat_service = chat_service
    if outbound_service is not None:
        app.state.whatsapp_outbound_service = outbound_service
    return app


def twilio_payload(message_sid: str = "SM123", sender: str = "+15551234567", body: str = "Hello") -> dict[str, str]:
    return {
        "MessageSid": message_sid,
        "From": sender,
        "Body": body,
        "To": "whatsapp:+15550001111",
        "ProfileName": "Test User",
        "WaId": "15551234567",
    }


def twilio_signature(url: str, payload: dict[str, str], auth_token: str) -> str:
    data = url
    for key in sorted(payload):
        data += key + payload[key]
    digest = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def install_fake_twilio_modules(monkeypatch: Any) -> None:
    twilio_module = ModuleType("twilio")
    request_validator_module = ModuleType("twilio.request_validator")
    twiml_module = ModuleType("twilio.twiml")
    messaging_response_module = ModuleType("twilio.twiml.messaging_response")

    class RequestValidator:
        def __init__(self, auth_token: str) -> None:
            self.auth_token = auth_token

        def validate(self, url: str, params: dict[str, str], signature: str) -> bool:
            expected = twilio_signature(url, params, self.auth_token)
            return hmac.compare_digest(expected, signature)

    class MessagingResponse:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def message(self, body: str) -> None:
            self.messages.append(body)

        def __str__(self) -> str:
            if not self.messages:
                return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
            body = ''.join(f'<Message>{escape(message)}</Message>' for message in self.messages)
            return f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'

    request_validator_module.RequestValidator = RequestValidator
    messaging_response_module.MessagingResponse = MessagingResponse
    twiml_module.messaging_response = messaging_response_module
    twilio_module.request_validator = request_validator_module
    twilio_module.twiml = twiml_module
    monkeypatch.setitem(sys.modules, "twilio", twilio_module)
    monkeypatch.setitem(sys.modules, "twilio.request_validator", request_validator_module)
    monkeypatch.setitem(sys.modules, "twilio.twiml", twiml_module)
    monkeypatch.setitem(sys.modules, "twilio.twiml.messaging_response", messaging_response_module)


def set_twilio_settings(
    monkeypatch: Any,
    *,
    enabled: bool = True,
    token: str = "test-auth-token",
    trust_forwarded_headers: bool = False,
) -> None:
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", token, raising=False)
    monkeypatch.setattr(settings, "TWILIO_SIGNATURE_VERIFICATION_ENABLED", enabled, raising=False)
    monkeypatch.setattr(settings, "TWILIO_TRUST_FORWARDED_HEADERS", trust_forwarded_headers, raising=False)


def test_valid_twilio_webhook_returns_xml_message(monkeypatch: Any) -> None:
    install_fake_twilio_modules(monkeypatch)
    set_twilio_settings(monkeypatch)

    chat_service = FakeChatService(response={"response": "Hello. I can help with your order."})
    outbound_service = FakeOutboundService()
    app = build_app(chat_service, outbound_service)

    payload = twilio_payload(body="Hi")
    url = "http://testserver/webhooks/twilio"
    signature = twilio_signature(url, payload, "test-auth-token")

    with TestClient(app) as client:
        response = client.post("/webhooks/twilio", data=payload, headers={"X-Twilio-Signature": signature})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "<Message>" in response.text
    assert "Hello. I can help with your order." in response.text
    assert chat_service.calls == [
        {
            "message": "Hi",
            "conversation_id": "+15551234567",
            "customer_phone": "+15551234567",
            "message_id": "SM123",
        }
    ]
    assert outbound_service.calls == []


def test_twilio_webhook_rejects_forwarded_public_url_signature_when_forwarded_headers_untrusted(monkeypatch: Any) -> None:
    install_fake_twilio_modules(monkeypatch)
    set_twilio_settings(monkeypatch, trust_forwarded_headers=False)

    chat_service = FakeChatService(response="Should not pass")
    app = build_app(chat_service)

    payload = twilio_payload(body="Hi from production")
    public_url = "https://demo.example.com/webhooks/twilio"
    signature = twilio_signature(public_url, payload, "test-auth-token")

    with TestClient(app) as client:
        response = client.post(
            "/webhooks/twilio",
            data=payload,
            headers={
                "X-Twilio-Signature": signature,
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "demo.example.com",
            },
        )

    assert response.status_code == 200
    assert response.text == '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    assert chat_service.calls == []


def test_twilio_webhook_accepts_forwarded_public_url_signature_when_forwarded_headers_trusted(monkeypatch: Any) -> None:
    install_fake_twilio_modules(monkeypatch)
    set_twilio_settings(monkeypatch, trust_forwarded_headers=True)

    chat_service = FakeChatService(response="Forwarded URL works")
    app = build_app(chat_service)

    payload = twilio_payload(body="Hi from production")
    public_url = "https://demo.example.com/webhooks/twilio"
    signature = twilio_signature(public_url, payload, "test-auth-token")

    with TestClient(app) as client:
        response = client.post(
            "/webhooks/twilio",
            data=payload,
            headers={
                "X-Twilio-Signature": signature,
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "demo.example.com",
            },
        )

    assert response.status_code == 200
    assert "Forwarded URL works" in response.text
    assert len(chat_service.calls) == 1


def test_menu_reply_text_is_returned_inside_message(monkeypatch: Any) -> None:
    install_fake_twilio_modules(monkeypatch)
    set_twilio_settings(monkeypatch)

    chat_service = FakeChatService(response={"response": "Menu: Chicken Biryani, Beef Burger, Fries"})
    outbound_service = FakeOutboundService()
    app = build_app(chat_service, outbound_service)

    payload = twilio_payload(body="menu")
    url = "http://testserver/webhooks/twilio"
    signature = twilio_signature(url, payload, "test-auth-token")

    with TestClient(app) as client:
        response = client.post("/webhooks/twilio", data=payload, headers={"X-Twilio-Signature": signature})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "<Message>" in response.text
    assert "Menu: Chicken Biryani, Beef Burger, Fries" in response.text
    assert outbound_service.calls == []


def test_duplicate_messagesid_does_not_repeat_processing(monkeypatch: Any) -> None:
    install_fake_twilio_modules(monkeypatch)
    set_twilio_settings(monkeypatch)

    chat_service = FakeChatService(response="Thanks!")
    outbound_service = FakeOutboundService()
    service = WhatsAppWebhookService(chat_service=chat_service, outbound_service=outbound_service)

    payload = twilio_payload(message_sid="SM-dup", body="Hello")

    first = __import__("asyncio").run(service.handle_twilio_webhook(payload))
    second = __import__("asyncio").run(service.handle_twilio_webhook(payload))

    assert first["status"] == "ok"
    assert first["processing_result"] == "processed"
    assert first["reply_text"] == "Thanks!"
    assert second["status"] == "duplicate"
    assert second["processing_result"] == "already_processed"
    assert len(chat_service.calls) == 1
    assert outbound_service.calls == []
