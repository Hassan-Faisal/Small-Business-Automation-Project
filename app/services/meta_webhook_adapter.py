from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from typing import Any, Mapping

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MetaInboundEvent:
    whatsapp_business_account_id: str | None
    phone_number_id: str | None
    sender_phone: str
    message_id: str
    timestamp: str
    message_type: str
    text_body: str


@dataclass(frozen=True, slots=True)
class MetaWebhookResult:
    status: str
    event: MetaInboundEvent | None = None
    reason: str | None = None


class MetaWebhookAdapter:
    """Parse and authenticate Meta webhooks without invoking application services."""

    def __init__(self) -> None:
        self._seen_message_ids: set[str] = set()

    @staticmethod
    def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
        if not settings.META_SIGNATURE_VERIFICATION_ENABLED:
            return True
        secret = settings.META_APP_SECRET.strip()
        if not secret or not signature_header:
            return False
        prefix, separator, supplied = signature_header.partition("=")
        if prefix != "sha256" or not separator or len(supplied) != 64:
            return False
        if any(character not in "0123456789abcdefABCDEF" for character in supplied):
            return False
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, supplied)

    def parse(self, payload: Mapping[str, Any]) -> MetaWebhookResult:
        if payload.get("object") not in (None, "whatsapp_business_account"):
            return MetaWebhookResult(status="ignored", reason="unsupported_object")
        entries = payload.get("entry")
        if not isinstance(entries, list):
            return MetaWebhookResult(status="ignored", reason="malformed_payload")

        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            waba_id = self._text(entry.get("id"))
            changes = entry.get("changes")
            if not isinstance(changes, list):
                continue
            for change in changes:
                if not isinstance(change, Mapping):
                    continue
                value = change.get("value")
                if not isinstance(value, Mapping):
                    continue
                metadata = value.get("metadata")
                phone_number_id = self._text(metadata.get("phone_number_id")) if isinstance(metadata, Mapping) else None
                messages = value.get("messages")
                if not isinstance(messages, list):
                    continue
                for message in messages:
                    if not isinstance(message, Mapping):
                        continue
                    message_type = self._text(message.get("type")) or "unknown"
                    if message_type != "text":
                        logger.info("Ignored unsupported Meta WhatsApp message", extra={"message_type": message_type})
                        continue
                    text = message.get("text")
                    body = self._text(text.get("body")) if isinstance(text, Mapping) else None
                    sender = self._text(message.get("from"))
                    message_id = self._text(message.get("id"))
                    timestamp = self._text(message.get("timestamp"))
                    if not body or not sender or not message_id or not timestamp:
                        continue
                    event = MetaInboundEvent(waba_id, phone_number_id, sender, message_id, timestamp, message_type, body)
                    if message_id in self._seen_message_ids:
                        logger.info("Ignored duplicate Meta WhatsApp message", extra={"message_id": message_id, "message_type": message_type})
                        return MetaWebhookResult(status="duplicate", event=event, reason="duplicate_message")
                    self._seen_message_ids.add(message_id)
                    return MetaWebhookResult(status="received", event=event)
        return MetaWebhookResult(status="ignored", reason="unsupported_or_malformed")

    @staticmethod
    def _text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def safe_json(payload: bytes) -> Mapping[str, Any] | None:
        try:
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return decoded if isinstance(decoded, Mapping) else None
