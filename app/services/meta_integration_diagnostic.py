from __future__ import annotations

from typing import Any, Mapping

import httpx

from app.core.config import settings
from app.services.whatsapp_outbound_provider import MetaWhatsAppOutboundProvider, build_whatsapp_outbound_provider


class MetaDiagnostic:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self.failures = 0
        self._subscribed_app_ids: list[str] = []
        self._phone_belongs_to_waba = False

    def close(self) -> None:
        self.client.close()

    def run(self, *, send_test: bool = False, mode: str = "text") -> int:
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
        self._check_waba(required)
        self._check_phone(required)
        self._check_subscription(required)
        self._check_phone_numbers(required)
        self._check_provider()
        callback = settings.META_WEBHOOK_PUBLIC_URL.strip()
        print(f"callback_url: {callback if callback else 'not_configured'}")
        self._print_asset_chain(required, callback)
        if send_test:
            self._send_test(mode)
        return 1 if self.failures else 0

    def _check_waba(self, required: dict[str, str]) -> None:
        waba_id = settings.META_WABA_ID.strip()
        if not waba_id or not required["WHATSAPP_ACCESS_TOKEN"] or not required["WHATSAPP_API_VERSION"]:
            self._skip("waba_query", "META_WABA_ID_or_configuration_missing")
            return
        result = self._get(f"/{waba_id}", {"fields": "id,name"})
        self._report_graph("waba_query", result)
        data = self._response_data(result)
        if data:
            print(f"waba_id: {self._safe_scalar(data.get('id')) or self._mask_id(waba_id)}")
            print(f"waba_name: {self._safe_scalar(data.get('name')) or 'not_returned'}")

    def _check_phone(self, required: dict[str, str]) -> None:
        if any(not value for value in required.values()):
            self._skip("phone_number_query", "configuration_missing")
            return
        result = self._get(
            f"/{required['WHATSAPP_PHONE_NUMBER_ID']}",
            {"fields": "id,display_phone_number,verified_name,quality_rating"},
        )
        self._report_graph("phone_number_query", result)
        data = self._response_data(result)
        if data:
            self._print_phone(data)

    def _check_subscription(self, required: dict[str, str]) -> None:
        waba_id = settings.META_WABA_ID.strip()
        if not waba_id or not required["WHATSAPP_ACCESS_TOKEN"] or not required["WHATSAPP_API_VERSION"]:
            self._skip("subscribed_apps_query", "META_WABA_ID_or_configuration_missing")
            return
        result = self._get(f"/{waba_id}/subscribed_apps", {})
        self._report_graph("subscribed_apps_query", result)
        data = self._response_data(result)
        entries = data.get("data") if isinstance(data, Mapping) else None
        if not isinstance(entries, list) or not entries:
            print("subscribed_apps: empty")
            return
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            nested = entry.get("whatsapp_business_api_data")
            app = nested if isinstance(nested, Mapping) else entry
            app_id = self._safe_scalar(app.get("id"))
            app_name = self._safe_scalar(app.get("name")) or "not_returned"
            fields = entry.get("subscribed_fields", app.get("subscribed_fields"))
            print(
                f"subscribed_app: app_id={self._mask_id(app_id) if app_id else 'not_returned'} "
                f"app_name={app_name} subscribed_fields={self._safe_fields(fields)}"
            )
            if app_id:
                self._subscribed_app_ids.append(app_id)

    def _check_phone_numbers(self, required: dict[str, str]) -> None:
        waba_id = settings.META_WABA_ID.strip()
        if not waba_id or not required["WHATSAPP_ACCESS_TOKEN"] or not required["WHATSAPP_API_VERSION"]:
            self._skip("phone_numbers_query", "META_WABA_ID_or_configuration_missing")
            return
        result = self._get(
            f"/{waba_id}/phone_numbers",
            {"fields": "id,display_phone_number,verified_name,quality_rating"},
        )
        self._report_graph("phone_numbers_query", result)
        data = self._response_data(result)
        numbers = data.get("data") if isinstance(data, Mapping) else None
        if not isinstance(numbers, list):
            numbers = []
        for phone in numbers:
            if isinstance(phone, Mapping):
                self._print_phone(phone)
                if self._safe_scalar(phone.get("id")) == required["WHATSAPP_PHONE_NUMBER_ID"]:
                    self._phone_belongs_to_waba = True
        if not self._phone_belongs_to_waba:
            self.failures += 1

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

    def _send_test(self, mode: str) -> None:
        recipient = safe_phone(settings.META_TEST_RECIPIENT_PHONE)
        if not recipient:
            self._fail("send_test: invalid_or_missing_META_TEST_RECIPIENT_PHONE")
            return
        try:
            provider = build_whatsapp_outbound_provider()
            if not isinstance(provider, MetaWhatsAppOutboundProvider):
                self._fail("send_test: provider_not_meta")
                return
            if mode == "template":
                result = provider.send_template_message(recipient_phone=recipient, template_name="hello_world", language_code="en_US")
            else:
                result = provider.send_text_message(recipient_phone=recipient, text="TiffinAI Meta diagnostic test.")
            if result.status == "sent":
                self._ok(f"send_test: {mode}")
            else:
                self._print_meta_error(provider)
                self._fail(f"send_test: {mode}: {result.reason or 'delivery_failed'}")
        except Exception:
            self._fail(f"send_test: {mode}: provider_error")

    def _print_meta_error(self, provider: MetaWhatsAppOutboundProvider) -> None:
        details = getattr(provider, "last_error_details", None)
        if not isinstance(details, dict):
            return
        secrets = (settings.WHATSAPP_ACCESS_TOKEN, settings.META_APP_SECRET, settings.WHATSAPP_VERIFY_TOKEN)
        for key in ("http_status", "type", "code", "error_subcode", "message", "error_data_details", "fbtrace_id"):
            value = details.get(key)
            if value is None:
                continue
            safe_value = str(value)
            for secret in secrets:
                if secret:
                    safe_value = safe_value.replace(secret, "[REDACTED]")
            label = "error.error_data.details" if key == "error_data_details" else f"error.{key}"
            if key == "http_status":
                label = "http_status"
            print(f"send_test_meta_error.{label}: {safe_value}")

    def _get(self, path: str, params: dict[str, str]) -> httpx.Response | None:
        try:
            return self.client.get(
                self._url(path),
                headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN.strip()}"},
                params=params,
            )
        except httpx.TimeoutException:
            return None
        except httpx.HTTPError:
            return None

    def _url(self, path: str) -> str:
        return f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION.strip()}{path}"

    @staticmethod
    def _response_data(response: httpx.Response | None) -> Mapping[str, Any] | None:
        if response is None or not response.is_success:
            return None
        try:
            payload = response.json()
        except (ValueError, TypeError):
            return None
        return payload if isinstance(payload, Mapping) else None

    @staticmethod
    def _safe_scalar(value: Any) -> str:
        return str(value).strip() if isinstance(value, (str, int)) and str(value).strip() else ""

    @staticmethod
    def _mask_id(value: str) -> str:
        if len(value) <= 4:
            return "*" * len(value)
        return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"

    @staticmethod
    def _mask_phone(value: Any) -> str:
        digits = "".join(character for character in str(value or "") if character.isdigit())
        return f"+{'*' * max(0, len(digits) - 4)}{digits[-4:]}" if digits else "not_returned"

    def _print_phone(self, phone: Mapping[str, Any]) -> None:
        print(
            "phone_number: "
            f"phone_number_id={self._mask_id(self._safe_scalar(phone.get('id'))) or 'not_returned'} "
            f"display_number={self._mask_phone(phone.get('display_phone_number'))} "
            f"verified_name={self._safe_scalar(phone.get('verified_name')) or 'not_returned'} "
            f"quality_rating={self._safe_scalar(phone.get('quality_rating')) or 'not_returned'}"
        )

    @staticmethod
    def _safe_fields(value: Any) -> str:
        if isinstance(value, list):
            return ",".join(str(item) for item in value if isinstance(item, (str, int))) or "not_returned"
        return str(value).strip() if isinstance(value, (str, int)) and str(value).strip() else "not_returned"

    def _print_asset_chain(self, required: dict[str, str], callback: str) -> None:
        expected_app_id = self._subscribed_app_ids[0] if self._subscribed_app_ids else "not_returned"
        print("asset_chain:")
        print(f"  expected_app_id={self._mask_id(expected_app_id) if expected_app_id != 'not_returned' else expected_app_id}")
        print(f"  subscribed_app_match={'true' if self._subscribed_app_ids else 'unknown'}")
        print(f"  configured_waba_id={self._mask_id(settings.META_WABA_ID.strip()) if settings.META_WABA_ID.strip() else 'not_configured'}")
        print(f"  configured_phone_number_id={self._mask_id(required['WHATSAPP_PHONE_NUMBER_ID']) if required['WHATSAPP_PHONE_NUMBER_ID'] else 'not_configured'}")
        print(f"  phone_belongs_to_waba={'true' if self._phone_belongs_to_waba else 'false'}")
        print(f"  callback_url_configured={'true' if bool(callback) else 'false'}")

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

