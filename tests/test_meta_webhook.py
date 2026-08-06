from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.meta import router
from app.core.config import settings
from app.services.meta_webhook_adapter import MetaWebhookAdapter


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def payload(message_type: str = "text", message_id: str = "wamid.1") -> dict[str, Any]:
    message: dict[str, Any] = {
        "from": "15551234567",
        "id": message_id,
        "timestamp": "1710000000",
        "type": message_type,
    }
    if message_type == "text":
        message["text"] = {"body": "Hello Meta"}
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "waba-123",
            "changes": [{"value": {
                "metadata": {"phone_number_id": "phone-123"},
                "messages": [message],
            }}],
        }],
    }


def signed_body(value: dict[str, Any], secret: str = "app-secret") -> tuple[bytes, dict[str, str]]:
    body = json.dumps(value).encode()
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, {"X-Hub-Signature-256": f"sha256={digest}"}


@pytest.fixture(autouse=True)
def meta_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "verify-token")
    monkeypatch.setattr(settings, "META_APP_SECRET", "app-secret")
    monkeypatch.setattr(settings, "META_SIGNATURE_VERIFICATION_ENABLED", True)


def test_valid_get_verification() -> None:
    with TestClient(build_app()) as client:
        response = client.get("/webhooks/meta", params={"hub.mode": "subscribe", "hub.verify_token": "verify-token", "hub.challenge": "challenge-123"})
    assert response.status_code == 200
    assert response.text == "challenge-123"
    assert response.headers["content-type"].startswith("text/plain")


def test_invalid_verify_token() -> None:
    with TestClient(build_app()) as client:
        response = client.get("/webhooks/meta", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "challenge-123"})
    assert response.status_code == 403
    assert response.json() == {"detail": "Meta webhook verification failed"}


def test_invalid_verification_mode() -> None:
    with TestClient(build_app()) as client:
        response = client.get("/webhooks/meta", params={"hub.mode": "not-subscribe", "hub.verify_token": "verify-token", "hub.challenge": "challenge-123"})
    assert response.status_code == 403


def test_valid_post_signature_and_text_extraction() -> None:
    body, headers = signed_body(payload())
    with TestClient(build_app()) as client:
        response = client.post("/webhooks/meta", content=body, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "received"}
    event_result = MetaWebhookAdapter().parse(payload())
    assert event_result.event is not None
    assert event_result.event.message_id == "wamid.1"
    assert event_result.event.text_body == "Hello Meta"

def test_invalid_post_signature() -> None:
    body = json.dumps(payload()).encode()
    with TestClient(build_app()) as client:
        response = client.post("/webhooks/meta", content=body, headers={"X-Hub-Signature-256": "sha256=invalid"})
    assert response.status_code == 403
    assert response.json() == {"detail": "Meta webhook signature invalid"}


def test_status_update_is_ignored_safely() -> None:
    status_payload = {"object": "whatsapp_business_account", "entry": [{"id": "waba-123", "changes": [{"value": {"statuses": [{"id": "status-1", "status": "delivered"}]}}]}]}
    body, headers = signed_body(status_payload)
    with TestClient(build_app()) as client:
        response = client.post("/webhooks/meta", content=body, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}


def test_unsupported_message_type_is_ignored_safely() -> None:
    body, headers = signed_body(payload(message_type="image"))
    with TestClient(build_app()) as client:
        response = client.post("/webhooks/meta", content=body, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}


def test_malformed_payload_returns_safe_200() -> None:
    body = b"not-json"
    digest = hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    with TestClient(build_app()) as client:
        response = client.post("/webhooks/meta", content=body, headers={"X-Hub-Signature-256": f"sha256={digest}"})
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}


def test_duplicate_message_is_suppressed() -> None:
    body, headers = signed_body(payload(message_id="wamid.duplicate"))
    with TestClient(build_app()) as client:
        first = client.post("/webhooks/meta", content=body, headers=headers)
        second = client.post("/webhooks/meta", content=body, headers=headers)
    assert first.json() == {"status": "received"}
    assert second.json() == {"status": "duplicate"}


def test_meta_route_does_not_invoke_application_services(monkeypatch: pytest.MonkeyPatch) -> None:
    body, headers = signed_body(payload())
    called = False

    def fail_if_called(*args: Any, **kwargs: Any) -> None:
        nonlocal called
        called = True
        raise AssertionError("application service must not be called")

    monkeypatch.setattr("app.services.whatsapp_transport.WhatsAppOutboundService", fail_if_called)
    with TestClient(build_app()) as client:
        response = client.post("/webhooks/meta", content=body, headers=headers)
    assert response.status_code == 200
    assert called is False
