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
    assert diagnostic.run() == 0
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
        def run(self, *, send_test: bool = False) -> int:
            assert send_test is False
            print("configuration: ok")
            return 0
        def close(self) -> None:
            self.client.close()
    monkeypatch.setattr("app.commands.meta_integration_diagnostic.MetaDiagnostic", NoSendDiagnostic)
    assert main([]) == 0
    assert "configuration: ok" in capsys.readouterr().out
