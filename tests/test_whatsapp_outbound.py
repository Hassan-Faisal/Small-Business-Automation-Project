from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from app.services.whatsapp_transport import WhatsAppOutboundService


@dataclass
class FakeResponse:
    response: httpx.Response

    async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> httpx.Response:
        self.request_args = {"url": url, "headers": headers, "json": json}
        return self.response


@dataclass
class ErroringClient:
    exc: Exception

    async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> httpx.Response:
        raise self.exc


def test_outbound_client_success(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "access-token", raising=False)
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "123456789", raising=False)
    monkeypatch.setattr(settings, "WHATSAPP_API_VERSION", "v20.0", raising=False)

    request = httpx.Request("POST", "https://graph.facebook.com/v20.0/123456789/messages")
    response = httpx.Response(200, request=request, json={"messages": [{"id": "wamid.1"}]})
    client = FakeResponse(response=response)
    service = WhatsAppOutboundService(client=client)  # type: ignore[arg-type]

    result = asyncio.run(service.send_text_message("15551234567", "Hello"))

    assert result["status"] == "ok"
    assert result["data"] == {"messages": [{"id": "wamid.1"}]}
    assert client.request_args["url"].endswith("/123456789/messages")
    assert client.request_args["json"]["text"]["body"] == "Hello"


def test_outbound_client_http_error(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "access-token", raising=False)
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "123456789", raising=False)
    monkeypatch.setattr(settings, "WHATSAPP_API_VERSION", "v20.0", raising=False)

    request = httpx.Request("POST", "https://graph.facebook.com/v20.0/123456789/messages")
    response = httpx.Response(500, request=request, text="server error")

    class RaisingClient:
        async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> httpx.Response:
            raise httpx.HTTPStatusError("boom", request=request, response=response)

    service = WhatsAppOutboundService(client=RaisingClient())  # type: ignore[arg-type]

    result = asyncio.run(service.send_text_message("15551234567", "Hello"))

    assert result["status"] == "error"
    assert result["status_code"] == 500
    assert "server error" in result["detail"]


def test_outbound_client_timeout(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "access-token", raising=False)
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "123456789", raising=False)
    monkeypatch.setattr(settings, "WHATSAPP_API_VERSION", "v20.0", raising=False)

    request = httpx.Request("POST", "https://graph.facebook.com/v20.0/123456789/messages")
    timeout_exc = httpx.ReadTimeout("timed out", request=request)
    service = WhatsAppOutboundService(client=ErroringClient(timeout_exc))  # type: ignore[arg-type]

    result = asyncio.run(service.send_text_message("15551234567", "Hello"))

    assert result["status"] == "timeout"
    assert "timed out" in result["detail"]
