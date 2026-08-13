from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from app.core.config import settings
from app.services.whatsapp_outbound_provider import MetaWhatsAppOutboundProvider
from app.services.whatsapp_transport import WhatsAppOutboundService
from app.services import whatsapp_transport


class ResponseClient:
    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response

    async def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]) -> httpx.Response:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_response(status: int, payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", "https://graph.facebook.com/messages"), json=payload)


def make_provider(monkeypatch: pytest.MonkeyPatch, response: httpx.Response | Exception) -> MetaWhatsAppOutboundProvider:
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "access-secret")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "phone-id")
    monkeypatch.setattr(settings, "WHATSAPP_API_VERSION", "v21.0")
    service = WhatsAppOutboundService(client=ResponseClient(response))
    return MetaWhatsAppOutboundProvider(service, send_runner=lambda awaitable: asyncio.run(awaitable))


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    captured: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(whatsapp_transport.logger, "info", lambda message, *, extra: captured.append((message, extra)))
    return captured


def test_success_returns_wamid_and_logs_safe_fields(monkeypatch: pytest.MonkeyPatch, logs: list[tuple[str, dict[str, Any]]]) -> None:
    provider = make_provider(monkeypatch, make_response(200, {"messages": [{"id": "wamid.success"}]}))
    result = provider.send_text_message(recipient_phone="923001234567", text="Hello customer")
    assert result.status == "sent"
    assert result.message_sid == "wamid.success"
    record = next(extra for message, extra in logs if message == "meta_outbound_request")
    assert record["http_status"] == 200
    assert record["success"] is True
    assert record["provider_message_id"] == "wamid.success"
    assert record["destination_phone_suffix"] == "4567"
    assert record["reply_length"] == 14


@pytest.mark.parametrize(
    ("status", "payload", "category"),
    [
        (400, {"error": {"type": "GraphMethodException", "code": 131051, "message": "Unsupported request"}}, "meta_api_error"),
        (401, {"error": {"type": "OAuthException", "code": 190, "message": "Invalid token"}}, "authentication_error"),
        (403, {"error": {"type": "OAuthException", "code": 10, "message": "Permission denied"}}, "permission_error"),
        (400, {"error": {"type": "OAuthException", "code": 131047, "error_subcode": 131047, "message": "Outside the 24 hour conversation window"}}, "conversation_window_error"),
        (429, {"error": {"type": "OAuthException", "code": 4, "message": "Rate limit"}}, "rate_limit_error"),
    ],
)
def test_meta_http_failures_are_classified_and_logged(monkeypatch: pytest.MonkeyPatch, logs: list[tuple[str, dict[str, Any]]], status: int, payload: dict[str, Any], category: str) -> None:
    provider = make_provider(monkeypatch, make_response(status, payload))
    result = provider.send_text_message(recipient_phone="923001234567", text="Hello")
    assert result.status == "failed"
    assert result.reason == category
    record = next(extra for message, extra in logs if message == "meta_outbound_request")
    assert record["http_status"] == status
    assert record["success"] is False
    assert record["safe_failure_category"] == category
    assert record["destination_phone_suffix"] == "4567"
    assert record["reply_length"] == 5


def test_timeout_is_transport_error(monkeypatch: pytest.MonkeyPatch, logs: list[tuple[str, dict[str, Any]]]) -> None:
    provider = make_provider(monkeypatch, httpx.TimeoutException("timed out"))
    result = provider.send_text_message(recipient_phone="923001234567", text="Hello")
    assert result.reason == "transport_error"
    record = next(extra for message, extra in logs if message == "meta_outbound_request")
    assert record["safe_failure_category"] == "transport_error"
    assert record["http_status"] is None


def test_network_error_is_transport_error(monkeypatch: pytest.MonkeyPatch, logs: list[tuple[str, dict[str, Any]]]) -> None:
    provider = make_provider(monkeypatch, httpx.ConnectError("network down"))
    result = provider.send_text_message(recipient_phone="923001234567", text="Hello")
    assert result.reason == "transport_error"
    assert next(extra for message, extra in logs if message == "meta_outbound_request")["safe_failure_category"] == "transport_error"


def test_logs_redact_secrets_phone_and_reply(monkeypatch: pytest.MonkeyPatch, logs: list[tuple[str, dict[str, Any]]]) -> None:
    monkeypatch.setattr(settings, "META_APP_SECRET", "app-secret")
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "verify-secret")
    provider = make_provider(monkeypatch, make_response(403, {"error": {"type": "OAuthException", "code": 10, "message": "access-secret app-secret verify-secret", "error_data": {"details": "access-secret detail"}, "fbtrace_id": "trace-1"}}))
    provider.send_text_message(recipient_phone="923001234567", text="PRIVATE REPLY")
    rendered = str(logs)
    assert "access-secret" not in rendered
    assert "app-secret" not in rendered
    assert "verify-secret" not in rendered
    assert "923001234567" not in rendered
    assert "PRIVATE REPLY" not in rendered
    assert "4567" in rendered
