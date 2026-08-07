from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from twilio.rest import Client

from app.core.config import settings
from app.schemas.order_notification import NotificationResult
from app.services.meta_graph_errors import classify_meta_failure, safe_exception_details
from app.services.whatsapp_transport import WhatsAppOutboundService

logger = logging.getLogger(__name__)


class WhatsAppOutboundProvider(Protocol):
    def send_text_message(self, *, recipient_phone: str, text: str) -> NotificationResult:
        if not settings.WHATSAPP_ACCESS_TOKEN.strip() or not settings.WHATSAPP_PHONE_NUMBER_ID.strip():
            return NotificationResult(status="skipped", reason="whatsapp_configuration_missing")
        ...


def normalize_whatsapp_address(value: str) -> str | None:
    raw = value.strip()
    if raw.lower().startswith("whatsapp:"):
        raw = raw.split(":", 1)[1].strip()
    compact = "".join(character for character in raw if character not in " ()-.")
    digits = compact[1:] if compact.startswith("+") else compact
    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        return None
    return f"whatsapp:+{digits}"


class TwilioWhatsAppOutboundProvider:
    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    def send_text_message(self, *, recipient_phone: str, text: str) -> NotificationResult:
        if not settings.WHATSAPP_ACCESS_TOKEN.strip() or not settings.WHATSAPP_PHONE_NUMBER_ID.strip():
            return NotificationResult(status="skipped", reason="whatsapp_configuration_missing")
        account_sid = settings.TWILIO_ACCOUNT_SID.strip()
        auth_token = settings.TWILIO_AUTH_TOKEN.strip()
        sender = normalize_whatsapp_address(settings.TWILIO_WHATSAPP_NUMBER)
        recipient = normalize_whatsapp_address(recipient_phone)
        if not account_sid or not auth_token or not sender:
            return NotificationResult(status="skipped", reason="twilio_configuration_missing")
        if not recipient:
            return NotificationResult(status="skipped", reason="invalid_customer_phone")
        try:
            client = self._client or Client(account_sid, auth_token)
            message = client.messages.create(body=text, from_=sender, to=recipient)
            return NotificationResult(status="sent", message_sid=str(message.sid))
        except Exception:
            return NotificationResult(status="failed", reason="twilio_api_error")


class MetaWhatsAppOutboundProvider:
    def __init__(self, outbound_service: WhatsAppOutboundService | None = None, *, send_runner: Callable[[Awaitable[dict[str, Any]]], dict[str, Any]] | None = None) -> None:
        self._outbound_service = outbound_service or WhatsAppOutboundService()
        self._send_runner = send_runner or asyncio.run
        self.last_error_details: dict[str, Any] | None = None

    def send_text_message(self, *, recipient_phone: str, text: str) -> NotificationResult:
        if not settings.WHATSAPP_ACCESS_TOKEN.strip() or not settings.WHATSAPP_PHONE_NUMBER_ID.strip():
            return NotificationResult(status="skipped", reason="whatsapp_configuration_missing")
        return self._send(recipient_phone, self._outbound_service.send_text_message(recipient_phone=recipient_phone, text=text))

    async def send_text_message_async(self, *, recipient_phone: str, text: str) -> NotificationResult:
        """Send on the caller's event loop so the shared AsyncClient remains loop-safe."""
        if not settings.WHATSAPP_ACCESS_TOKEN.strip() or not settings.WHATSAPP_PHONE_NUMBER_ID.strip():
            return NotificationResult(status="skipped", reason="whatsapp_configuration_missing")
        self.last_error_details = None
        try:
            result = await self._outbound_service.send_text_message(recipient_phone=recipient_phone, text=text)
        except Exception as exc:
            details = safe_exception_details(exc, (settings.WHATSAPP_ACCESS_TOKEN, settings.META_APP_SECRET, settings.WHATSAPP_VERIFY_TOKEN))
            self.last_error_details = details
            logger.exception("meta_outbound_provider_exception", extra={"event": "meta_outbound_provider_exception", "destination_phone_suffix": recipient_phone[-4:], **details, "safe_failure_category": "provider_exception"})
            return NotificationResult(status="failed", reason="provider_exception")
        error_details = result.get("error_details")
        if isinstance(error_details, dict):
            self.last_error_details = error_details
        if result.get("status") == "ok":
            data = result.get("data")
            messages = data.get("messages") if isinstance(data, dict) else None
            sid = messages[0].get("id") if isinstance(messages, list) and messages and isinstance(messages[0], dict) else None
            return NotificationResult(status="sent", message_sid=str(sid) if sid else None)
        if result.get("status") == "skipped":
            return NotificationResult(status="skipped", reason="meta_transport_skipped")
        category = "transport_error" if result.get("status") == "timeout" or result.get("transport_error") else ("provider_error" if result.get("status") == "error" and not self.last_error_details else classify_meta_failure(self.last_error_details, status_code=result.get("status_code") if isinstance(result.get("status_code"), int) else None))
        return NotificationResult(status="failed", reason=category)
    def send_template_message(self, *, recipient_phone: str, template_name: str, language_code: str) -> NotificationResult:
        if not settings.WHATSAPP_ACCESS_TOKEN.strip() or not settings.WHATSAPP_PHONE_NUMBER_ID.strip():
            return NotificationResult(status="skipped", reason="whatsapp_configuration_missing")
        return self._send(recipient_phone, self._outbound_service.send_template_message(recipient_phone=recipient_phone, template_name=template_name, language_code=language_code))

    def _send(self, recipient_phone: str, awaitable: Awaitable[dict[str, Any]]) -> NotificationResult:
        self.last_error_details = None
        if not settings.WHATSAPP_ACCESS_TOKEN.strip() or not settings.WHATSAPP_PHONE_NUMBER_ID.strip():
            return NotificationResult(status="skipped", reason="whatsapp_configuration_missing")
        try:
            result = self._send_runner(awaitable)
        except Exception as exc:
            details = safe_exception_details(exc, (settings.WHATSAPP_ACCESS_TOKEN, settings.META_APP_SECRET, settings.WHATSAPP_VERIFY_TOKEN))
            self.last_error_details = details
            logger.exception("meta_outbound_provider_exception", extra={"event": "meta_outbound_provider_exception", "destination_phone_suffix": recipient_phone[-4:], **details, "safe_failure_category": "provider_exception"})
            return NotificationResult(status="failed", reason="provider_exception")
        error_details = result.get("error_details")
        if isinstance(error_details, dict):
            self.last_error_details = error_details
        if result.get("status") == "ok":
            data = result.get("data")
            messages = data.get("messages") if isinstance(data, dict) else None
            sid = messages[0].get("id") if isinstance(messages, list) and messages and isinstance(messages[0], dict) else None
            return NotificationResult(status="sent", message_sid=str(sid) if sid else None)
        if result.get("status") == "skipped":
            return NotificationResult(status="skipped", reason="meta_transport_skipped")
        category = "transport_error" if result.get("status") == "timeout" or result.get("transport_error") else ("provider_error" if result.get("status") == "error" and not self.last_error_details else classify_meta_failure(self.last_error_details, status_code=result.get("status_code") if isinstance(result.get("status_code"), int) else None))
        return NotificationResult(status="failed", reason=category)

class UnsupportedWhatsAppOutboundProvider:
    def send_text_message(self, *, recipient_phone: str, text: str) -> NotificationResult:
        if not settings.WHATSAPP_ACCESS_TOKEN.strip() or not settings.WHATSAPP_PHONE_NUMBER_ID.strip():
            return NotificationResult(status="skipped", reason="whatsapp_configuration_missing")
        return NotificationResult(status="failed", reason="unsupported_outbound_provider")


def build_whatsapp_outbound_provider() -> WhatsAppOutboundProvider:
    provider = getattr(settings, "WHATSAPP_OUTBOUND_PROVIDER", "twilio").strip().lower()
    if provider == "twilio":
        return TwilioWhatsAppOutboundProvider()
    if provider == "meta":
        return MetaWhatsAppOutboundProvider()
    return UnsupportedWhatsAppOutboundProvider()
