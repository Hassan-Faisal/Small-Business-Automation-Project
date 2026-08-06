from __future__ import annotations

from typing import Any

from app.commands.meta_whatsapp_smoke_test import run_smoke_test
from app.core.config import settings
from app.schemas.order_notification import NotificationResult


class FakeMetaProvider:
    def __init__(self, result: NotificationResult | None = None, error: Exception | None = None) -> None:
        self.result = result or NotificationResult(status="sent", message_sid="wamid.test-1")
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def send_text_message(self, *, recipient_phone: str, text: str) -> NotificationResult:
        self.calls.append({"recipient_phone": recipient_phone, "text": text})
        if self.error:
            raise self.error
        return self.result


def configure(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "secret-access-token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "phone-number-id")
    monkeypatch.setattr(settings, "WHATSAPP_API_VERSION", "v21.0")
    monkeypatch.setattr(settings, "META_TEST_RECIPIENT_PHONE", "+92 (300) 123-4567")


def test_successful_delivery_and_safe_normalization(monkeypatch, capsys) -> None:
    configure(monkeypatch)
    provider = FakeMetaProvider()
    assert run_smoke_test(lambda: provider) == 0
    assert provider.calls[0]["recipient_phone"] == "923001234567"
    assert "status: sent" in capsys.readouterr().out


def test_message_id_extraction(monkeypatch, capsys) -> None:
    configure(monkeypatch)
    provider = FakeMetaProvider(NotificationResult(status="sent", message_sid="wamid.extracted"))
    run_smoke_test(lambda: provider)
    assert "message_id: wamid.extracted" in capsys.readouterr().out


def test_missing_configuration(monkeypatch, capsys) -> None:
    configure(monkeypatch)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
    assert run_smoke_test(lambda: (_ for _ in ()).throw(AssertionError("called"))) == 1
    assert capsys.readouterr().out == "status: skipped\nreason: missing_configuration\n"


def test_invalid_number(monkeypatch, capsys) -> None:
    configure(monkeypatch)
    monkeypatch.setattr(settings, "META_TEST_RECIPIENT_PHONE", "not-a-phone")
    assert run_smoke_test(lambda: (_ for _ in ()).throw(AssertionError("called"))) == 1
    assert "reason: invalid_recipient_phone" in capsys.readouterr().out


def test_meta_graph_api_error(monkeypatch, capsys) -> None:
    configure(monkeypatch)
    provider = FakeMetaProvider(NotificationResult(status="failed", reason="provider_error"))
    assert run_smoke_test(lambda: provider) == 1
    assert capsys.readouterr().out == "status: failed\nreason: provider_error\n"


def test_timeout(monkeypatch, capsys) -> None:
    configure(monkeypatch)
    provider = FakeMetaProvider(NotificationResult(status="failed", reason="timeout"))
    assert run_smoke_test(lambda: provider) == 1
    assert "reason: timeout" in capsys.readouterr().out


def test_secret_redaction(monkeypatch, capsys) -> None:
    configure(monkeypatch)
    provider = FakeMetaProvider(error=RuntimeError("secret-access-token phone-number-id"))
    assert run_smoke_test(lambda: provider) == 1
    output = capsys.readouterr().out
    assert "secret-access-token" not in output
    assert "phone-number-id" not in output
