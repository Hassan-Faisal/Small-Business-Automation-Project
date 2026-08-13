from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.services.meta_embedded_signup import MetaEmbeddedSignupError, MetaEmbeddedSignupService


class FakeClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.params: dict[str, str] | None = None

    def get(self, url: str, *, params: dict[str, str]) -> httpx.Response:
        self.params = params
        return self.response


def test_exchange_code_succeeds_without_returning_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "META_APP_ID", "app-id")
    monkeypatch.setattr(settings, "META_APP_SECRET", "app-secret")
    response = httpx.Response(200, json={"access_token": "secret-token", "token_type": "bearer"})
    client = FakeClient(response)

    assert MetaEmbeddedSignupService(client=client).exchange_code("one-time-code") is True
    assert client.params == {"client_id": "app-id", "client_secret": "app-secret", "code": "one-time-code"}


def test_exchange_code_rejects_meta_error_without_leaking_credentials(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(settings, "META_APP_ID", "app-id")
    monkeypatch.setattr(settings, "META_APP_SECRET", "app-secret")
    response = httpx.Response(400, json={"error": {"message": "bad app-secret one-time-code"}})

    with pytest.raises(MetaEmbeddedSignupError):
        MetaEmbeddedSignupService(client=FakeClient(response)).exchange_code("one-time-code")

    assert "app-secret" not in caplog.text
    assert "one-time-code" not in caplog.text
