from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.commands.meta_integration_diagnostic import main
from app.core.config import settings
from app.services.meta_integration_diagnostic import MetaDiagnostic


class FakeClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        return self.response

    def close(self) -> None:
        pass



class FakeResponse:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.request_args: dict[str, Any] = {}

    async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> httpx.Response:
        self.request_args = {"url": url, "headers": headers, "json": json}
        return self.response


class FakeOutbound:
    async def send_text_message(self, recipient_phone: str, text: str) -> dict[str, Any]:
        return {"status": "ok", "data": {"messages": [{"id": "wamid.test"}]}}

    async def send_template_message(self, recipient_phone: str, template_name: str, language_code: str) -> dict[str, Any]:
        return {"status": "ok", "data": {"messages": [{"id": "wamid.template"}]}}

def configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "super-secret-token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "phone-123")
    monkeypatch.setattr(settings, "WHATSAPP_API_VERSION", "v21.0")
    monkeypatch.setattr(settings, "WHATSAPP_OUTBOUND_PROVIDER", "meta")
    monkeypatch.setattr(settings, "META_WABA_ID", "waba-123")
    monkeypatch.setattr(settings, "META_WEBHOOK_PUBLIC_URL", "https://example.test/webhooks/meta")


def test_diagnostic_redacts_secrets_and_reports_safe_categories(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    configure(monkeypatch)
    response = httpx.Response(200, request=httpx.Request("GET", "https://graph.facebook.com"), json={"data": []})
    diagnostic = MetaDiagnostic(FakeClient(response))
    assert diagnostic.run() == 1
    output = capsys.readouterr().out
    assert "super-secret-token" not in output
    assert "phone-123" not in output
    assert "configuration: ok" in output
    assert "callback_url: https://example.test/webhooks/meta" in output


def test_diagnostic_missing_configuration_is_nonzero(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    configure(monkeypatch)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
    response = httpx.Response(200, request=httpx.Request("GET", "https://graph.facebook.com"), json={})
    diagnostic = MetaDiagnostic(FakeClient(response))
    assert diagnostic.run() == 1
    output = capsys.readouterr().out
    assert "configuration: missing WHATSAPP_ACCESS_TOKEN: failed" in output
    assert "super-secret-token" not in output


def test_command_does_not_send_without_flag(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    configure(monkeypatch)
    class NoSendDiagnostic:
        def __init__(self, client):
            self.client = client
        def run(self, *, send_test: bool = False, mode: str = "text") -> int:
            assert send_test is False
            print("configuration: ok")
            return 0
        def close(self) -> None:
            self.client.close()
    monkeypatch.setattr("app.commands.meta_integration_diagnostic.MetaDiagnostic", NoSendDiagnostic)
    assert main([]) == 0
    assert "configuration: ok" in capsys.readouterr().out


def test_meta_provider_preserves_safe_graph_error_details(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings
    from app.services.whatsapp_outbound_provider import MetaWhatsAppOutboundProvider
    from app.services.whatsapp_transport import WhatsAppOutboundService

    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "access-secret")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "phone-id")
    request = httpx.Request("POST", "https://graph.facebook.com/v25.0/phone-id/messages")
    response = httpx.Response(403, request=request, json={"error": {"type": "OAuthException", "code": 10, "error_subcode": 131000, "message": "Token access-secret rejected", "error_data": {"details": "secret-access-token detail"}, "fbtrace_id": "trace-1", "authorization": "Bearer access-secret"}})
    service = WhatsAppOutboundService(client=FakeResponse(response=response))
    provider = MetaWhatsAppOutboundProvider(outbound_service=service, send_runner=lambda awaitable: __import__("asyncio").run(awaitable))
    result = provider.send_text_message(recipient_phone="923001234567", text="hello")
    assert result.status == "failed"
    assert provider.last_error_details == {"http_status": 403, "type": "OAuthException", "code": 10, "error_subcode": 131000, "message": "Token access-secret rejected", "error_data_details": "secret-access-token detail", "fbtrace_id": "trace-1"}


def test_meta_template_payload_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings
    from app.services.whatsapp_transport import WhatsAppOutboundService

    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "access-secret")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "phone-id")
    request = httpx.Request("POST", "https://graph.facebook.com/v25.0/phone-id/messages")
    response = httpx.Response(200, request=request, json={"messages": [{"id": "wamid.template"}]})
    client = FakeResponse(response=response)
    service = WhatsAppOutboundService(client=client)
    result = __import__("asyncio").run(service.send_template_message("923001234567", "hello_world", "en_US"))
    assert result["status"] == "ok"
    assert client.request_args["json"] == {"messaging_product": "whatsapp", "to": "923001234567", "type": "template", "template": {"name": "hello_world", "language": {"code": "en_US"}}}


def test_diagnostic_prints_only_safe_error_fields(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from app.commands.meta_integration_diagnostic import MetaDiagnostic
    from app.core.config import settings
    from app.services.whatsapp_outbound_provider import MetaWhatsAppOutboundProvider

    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "access-secret")
    monkeypatch.setattr(settings, "META_APP_SECRET", "app-secret")
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "verify-secret")
    provider = MetaWhatsAppOutboundProvider(outbound_service=FakeOutbound())
    provider.last_error_details = {"http_status": 403, "type": "OAuthException", "code": 10, "error_subcode": 131000, "message": "bad access-secret", "error_data_details": "app-secret detail", "fbtrace_id": "trace-1", "authorization": "Bearer access-secret"}
    diagnostic = MetaDiagnostic(FakeClient(httpx.Response(200, request=httpx.Request("GET", "https://graph.facebook.com"))))
    diagnostic._print_meta_error(provider)
    output = capsys.readouterr().out
    assert "http_status: 403" in output
    assert "error.type: OAuthException" in output
    assert "error.code: 10" in output
    assert "error.error_subcode: 131000" in output
    assert "error.error_data.details: [REDACTED] detail" in output
    assert "error.fbtrace_id: trace-1" in output
    assert "access-secret" not in output
    assert "app-secret" not in output
    assert "authorization" not in output


class SequenceClient(FakeClient):
    def __init__(self, responses: list[httpx.Response]) -> None:
        super().__init__(responses[0])
        self.responses = responses
        self.index = 0

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        response = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return response


def response(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, request=httpx.Request("GET", "https://graph.facebook.com"), json=payload)


def test_diagnostic_reports_waba_phone_relationship_and_masks_assets(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    configure(monkeypatch)
    client = SequenceClient([
        response({"id": "waba-123", "name": "Kitchen WABA"}),
        response({"id": "phone-123", "display_phone_number": "+923001234567", "verified_name": "Kitchen", "quality_rating": "GREEN"}),
        response({"data": [{"whatsapp_business_api_data": {"id": "app-987654", "name": "Kitchen App"}, "subscribed_fields": ["messages"]}]}),
        response({"data": [{"id": "phone-123", "display_phone_number": "+923001234567", "verified_name": "Kitchen", "quality_rating": "GREEN"}]}),
    ])
    assert MetaDiagnostic(client).run() == 0
    output = capsys.readouterr().out
    assert "waba_name: Kitchen WABA" in output
    assert "subscribed_app: app_id=ap******54 app_name=Kitchen App subscribed_fields=messages" in output
    assert "display_number=+********4567" in output
    assert "phone_belongs_to_waba=true" in output
    assert "subscribed_app_match=true" in output
    assert "phone-123" not in output
    assert "923001234567" not in output


def test_diagnostic_reports_mismatched_phone_id(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    configure(monkeypatch)
    client = SequenceClient([
        response({"id": "waba-123", "name": "Kitchen WABA"}),
        response({"id": "phone-123", "display_phone_number": "+923001234567"}),
        response({"data": [{"id": "app-1", "name": "Kitchen App", "subscribed_fields": ["messages"]}]}),
        response({"data": [{"id": "different-phone", "display_phone_number": "+923001111111"}]}),
    ])
    assert MetaDiagnostic(client).run() == 1
    assert "phone_belongs_to_waba=false" in capsys.readouterr().out


def test_diagnostic_reports_unknown_subscription_match_when_empty(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    configure(monkeypatch)
    client = SequenceClient([
        response({"id": "waba-123", "name": "Kitchen WABA"}),
        response({"id": "phone-123", "display_phone_number": "+923001234567"}),
        response({"data": []}),
        response({"data": [{"id": "phone-123"}]}),
    ])
    assert MetaDiagnostic(client).run() == 0
    output = capsys.readouterr().out
    assert "subscribed_apps: empty" in output
    assert "subscribed_app_match=unknown" in output




