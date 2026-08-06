from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.core.config import settings
from app.schemas.order_notification import NotificationResult
from app.services.meta_webhook_adapter import MetaInboundEvent
from app.services.whatsapp_outbound_provider import MetaWhatsAppOutboundProvider, WhatsAppOutboundProvider, build_whatsapp_outbound_provider

logger = logging.getLogger(__name__)


def normalize_meta_conversation_id(sender_phone: str) -> str:
    digits = "".join(character for character in sender_phone if character.isdigit())
    return f"whatsapp:+{digits}"


def _reply_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("response", "reply_text", "message", "content", "text"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return str(value).strip() if value is not None else ""


class MetaMessageProcessingService:
    def __init__(self, chat_service: Any, provider: WhatsAppOutboundProvider | None = None) -> None:
        self.chat_service = chat_service
        self.provider = provider or build_whatsapp_outbound_provider()

    async def process(self, event: MetaInboundEvent) -> None:
        started = time.perf_counter()
        conversation_id = normalize_meta_conversation_id(event.sender_phone)
        logger.info("meta_message_normalized", extra={"event": "meta_message_normalized", "message_id": event.message_id, "sender_phone_suffix": event.sender_phone[-4:], "phone_number_id": event.phone_number_id, "message_type": event.message_type, "text_length": len(event.text_body)})
        if settings.WHATSAPP_OUTBOUND_PROVIDER.strip().lower() != "meta" or not isinstance(self.provider, MetaWhatsAppOutboundProvider):
            self._processing_log(event, conversation_id, "provider_not_meta", 0, started)
            return
        try:
            reply = await self.chat_service.chat(message=event.text_body, conversation_id=conversation_id, customer_phone=conversation_id, message_id=event.message_id)
            reply_text = _reply_text(reply)
        except Exception:
            logger.exception("meta_message_processing_result", extra={"event": "meta_message_processing_result", "message_id": event.message_id, "conversation_id": conversation_id, "result": "chat_service_failed", "reply_length": 0, "duration_ms": self._duration(started)})
            return
        if not reply_text:
            self._processing_log(event, conversation_id, "empty_reply", 0, started)
            return
        try:
            result: NotificationResult = await asyncio.to_thread(self.provider.send_text_message, recipient_phone=event.sender_phone, text=reply_text)
        except Exception:
            logger.exception("meta_outbound_result", extra={"event": "meta_outbound_result", "message_id": event.message_id, "provider": "meta", "status": "failed", "provider_message_id": None, "safe_failure_category": "provider_exception"})
            self._processing_log(event, conversation_id, "outbound_failed", len(reply_text), started)
            return
        logger.info("meta_outbound_result", extra={"event": "meta_outbound_result", "message_id": event.message_id, "provider": "meta", "status": result.status, "provider_message_id": result.message_sid, "safe_failure_category": result.reason})
        self._processing_log(event, conversation_id, "outbound_sent" if result.status == "sent" else "outbound_failed", len(reply_text), started)

    @staticmethod
    def _duration(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)

    def _processing_log(self, event: MetaInboundEvent, conversation_id: str, result: str, reply_length: int, started: float) -> None:
        logger.info("meta_message_processing_result", extra={"event": "meta_message_processing_result", "message_id": event.message_id, "conversation_id": conversation_id, "result": result, "reply_length": reply_length, "duration_ms": self._duration(started)})
