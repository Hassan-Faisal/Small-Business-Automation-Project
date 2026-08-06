from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn

from app.core.config import settings
from app.schemas.order_notification import NotificationResult
from app.services.whatsapp_outbound_provider import MetaWhatsAppOutboundProvider

SMOKE_TEST_MESSAGE = "TiffinAI Meta Cloud API connection test."


def normalize_meta_recipient(value: str) -> str | None:
    """Return a WhatsApp Cloud API recipient as digits only."""
    raw = value.strip()
    if raw.lower().startswith("whatsapp:"):
        raw = raw.split(":", 1)[1].strip()
    compact = "".join(character for character in raw if character not in " ()-.")
    digits = compact[1:] if compact.startswith("+") else compact
    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        return None
    return digits


def _print_failure(status: str, reason: str) -> int:
    print(f"status: {status}")
    print(f"reason: {reason}")
    return 1


def run_smoke_test(provider_factory: Callable[[], MetaWhatsAppOutboundProvider] = MetaWhatsAppOutboundProvider) -> int:
    required = {
        "WHATSAPP_ACCESS_TOKEN": settings.WHATSAPP_ACCESS_TOKEN.strip(),
        "WHATSAPP_PHONE_NUMBER_ID": settings.WHATSAPP_PHONE_NUMBER_ID.strip(),
        "WHATSAPP_API_VERSION": settings.WHATSAPP_API_VERSION.strip(),
        "META_TEST_RECIPIENT_PHONE": settings.META_TEST_RECIPIENT_PHONE.strip(),
    }
    if any(not value for value in required.values()):
        return _print_failure("skipped", "missing_configuration")
    recipient = normalize_meta_recipient(required["META_TEST_RECIPIENT_PHONE"])
    if recipient is None:
        return _print_failure("failed", "invalid_recipient_phone")
    try:
        result: NotificationResult = provider_factory().send_text_message(recipient_phone=recipient, text=SMOKE_TEST_MESSAGE)
    except Exception:
        return _print_failure("failed", "provider_error")
    if result.status == "sent":
        print("status: sent")
        if result.message_sid:
            print(f"message_id: {result.message_sid}")
        return 0
    return _print_failure(result.status, result.reason or "provider_error")


def main() -> NoReturn:
    raise SystemExit(run_smoke_test())


if __name__ == "__main__":
    main()
