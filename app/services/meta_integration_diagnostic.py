from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.services.whatsapp_outbound_provider import MetaWhatsAppOutboundProvider, build_whatsapp_outbound_provider


class MetaDiagnostic:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self.failures = 0

    def close(self) -> None:
        self.client.close()

    def run(self, *, send_test: bool = False) -> int:
        required = {
            "WHATSAPP_ACCESS_TOKEN": settings.WHATSAPP_ACCESS_TOKEN.strip(),
            "WHATSAPP_PHONE_NUMBER_ID": settings.WHATSAPP_PHONE_NUMBER_ID.strip(),
            "WHATSAPP_API_VERSION": settings.WHATSAPP_API_VERSION.strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if settings.WHATSAPP_OUTBOUND_PROVIDER.strip().lower() != "meta":
            missing.append("WHATSAPP_OUTBOUND_PROVIDER=meta")
        if missing:
            self._fail(f"configuration: missing {','.join(missing)}")
        else:
            self._ok("configuration")
        self._check_phone(required)
        self._check_subscription(required)
        self._check_provider()
        callback = settings.META_WEBHOOK_PUBLIC_URL.strip()
        print(f"callback_url: {callback if callback else 'not_configured'}")
        if send_test:
            self._send_test()
        return 1 if self.failures else 0

    def _check_phone(self, required: dict[str, str]) -> None:
        if any(not value for value in required.values()):
            self._skip("phone_number_query", "configuration_missing")
            return
        result = self._get(f"/{required['WHATSAPP_PHONE_NUMBER_ID']}", {"fields": "id,display_phone_number,verified_name"})
        self._report_graph("phone_number_query", result)

    def _check_subscription(self, required: dict[str, str]) -> None:
        waba_id = settings.META_WABA_ID.strip()
        if not waba_id or not required["WHATSAPP_ACCESS_TOKEN"] or not required["WHATSAPP_API_VERSION"]:
            self._skip("subscribed_apps_query", "META_WABA_ID_or_configuration_missing")
            return
        result = self._get(f"/{waba_id}/subscribed_apps", {})
        self._report_graph("subscribed_apps_query", result)

    def _check_provider(self) -> None:
        try:
            provider = build_whatsapp_outbound_provider()
        except Exception:
            self._fail("outbound_provider: construction_failed")
            return
        if isinstance(provider, MetaWhatsAppOutboundProvider):
            self._ok("outbound_provider")
        else:
            self._fail("outbound_provider: not_meta")

    def _send_test(self) -> None:
        recipient = safe_phone(settings.META_TEST_RECIPIENT_PHONE)
        if not recipient:
            self._fail("send_test: invalid_or_missing_META_TEST_RECIPIENT_PHONE")
            return
        try:
            provider = build_whatsapp_outbound_provider()
            if not isinstance(provider, MetaWhatsAppOutboundProvider):
                self._fail("send_test: provider_not_meta")
                return
            result = provider.send_text_message(recipient_phone=recipient, text="TiffinAI Meta diagnostic test.")
            if result.status == "sent":
                self._ok("send_test")
            else:
                self._fail(f"send_test: {result.reason or 'delivery_failed'}")
        except Exception:
            self._fail("send_test: provider_error")

    def _get(self, path: str, params: dict[str, str]) -> httpx.Response | None:
        try:
            return self.client.get(self._url(path), headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN.strip()}"}, params=params)
        except httpx.TimeoutException:
            return None
        except httpx.HTTPError:
            return None

    def _url(self, path: str) -> str:
        return f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION.strip()}{path}"

    def _report_graph(self, label: str, response: httpx.Response | None) -> None:
        if response is not None and response.is_success:
            self._ok(label)
        elif response is not None and response.status_code in {401, 403}:
            self._fail(f"{label}: authorization_failed")
        elif response is not None:
            self._fail(f"{label}: graph_api_error")
        else:
            self._fail(f"{label}: timeout_or_transport_error")

    def _ok(self, label: str) -> None:
        print(f"{label}: ok")

    def _skip(self, label: str, reason: str) -> None:
        print(f"{label}: skipped ({reason})")

    def _fail(self, label: str) -> None:
        self.failures += 1
        print(f"{label}: failed")


def safe_phone(value: str) -> str | None:
    raw = value.strip()
    if raw.lower().startswith("whatsapp:"):
        raw = raw.split(":", 1)[1].strip()
    compact = "".join(character for character in raw if character not in " ()-.")
    digits = compact[1:] if compact.startswith("+") else compact
    return digits if digits.isdigit() and 8 <= len(digits) <= 15 else None
