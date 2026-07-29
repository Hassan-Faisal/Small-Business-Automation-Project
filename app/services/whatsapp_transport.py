from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import setup_logger

logger = setup_logger(__name__)


class WhatsAppOutboundService:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))

    async def send_text_message(self, recipient_phone: str, text: str) -> dict[str, Any]:
        access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", None)
        phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
        api_version = getattr(settings, "WHATSAPP_API_VERSION", "v20.0")

        if not access_token or not phone_number_id:
            logger.info(
                "whatsapp_outbound_skipped",
                extra={
                    "event": "whatsapp_outbound_skipped",
                    "recipient_phone": recipient_phone,
                    "reason": "not_configured",
                },
            )
            return {"status": "skipped"}

        url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "text",
            "text": {"body": text},
        }

        try:
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "whatsapp_outbound_sent",
                extra={
                    "event": "whatsapp_outbound_sent",
                    "recipient_phone": recipient_phone,
                    "text_length": len(text),
                    "status_code": response.status_code,
                },
            )
            return {"status": "ok", "data": data}
        except httpx.TimeoutException as exc:
            logger.warning(
                "whatsapp_outbound_timeout",
                extra={
                    "event": "whatsapp_outbound_timeout",
                    "recipient_phone": recipient_phone,
                },
            )
            return {"status": "timeout", "detail": str(exc)}
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "whatsapp_outbound_http_error",
                extra={
                    "event": "whatsapp_outbound_http_error",
                    "recipient_phone": recipient_phone,
                    "status_code": exc.response.status_code,
                },
            )
            return {"status": "error", "status_code": exc.response.status_code, "detail": exc.response.text}
        except httpx.HTTPError as exc:
            logger.warning(
                "whatsapp_outbound_error",
                extra={
                    "event": "whatsapp_outbound_error",
                    "recipient_phone": recipient_phone,
                },
            )
            return {"status": "error", "detail": str(exc)}


class WhatsAppWebhookService:
    def __init__(
        self,
        chat_service: Any,
        outbound_service: WhatsAppOutboundService | None = None,
        signature_secret: str | None = None,
        verify_token: str | None = None,
    ) -> None:
        self.chat_service = chat_service
        self.outbound_service = outbound_service or WhatsAppOutboundService()
        self.signature_secret = signature_secret or getattr(settings, "WHATSAPP_WEBHOOK_SECRET", None)
        self.verify_token = verify_token or getattr(settings, "WHATSAPP_VERIFY_TOKEN", None)
        self._seen_message_ids: set[str] = set()

    def verify_webhook(
        self,
        hub_mode: str | None,
        hub_verify_token: str | None,
        hub_challenge: str | None,
    ) -> tuple[int, str]:
        if hub_mode == "subscribe" and hub_verify_token == self.verify_token:
            return 200, hub_challenge or ""
        return 403, "Verification failed"

    @staticmethod
    def _coerce_reply_text(reply: Any) -> str:
        if reply is None:
            return ""

        if isinstance(reply, str):
            return reply.strip()

        if isinstance(reply, Mapping):
            for key in ("reply_text", "response", "message", "content", "text"):
                value = reply.get(key)

                if isinstance(value, str) and value.strip():
                    return value.strip()

                if isinstance(value, Mapping):
                    nested_text = WhatsAppWebhookService._coerce_reply_text(value)
                    if nested_text:
                        return nested_text

        response_attribute = getattr(reply, "response", None)
        if isinstance(response_attribute, str):
            return response_attribute.strip()

        content_attribute = getattr(reply, "content", None)
        if isinstance(content_attribute, str):
            return content_attribute.strip()

        return ""

    def _verify_signature(self, payload: bytes, signature_header: str | None) -> bool:
        if not self.signature_secret or not signature_header:
            return True

        expected = hmac.new(self.signature_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature_header, f"sha256={expected}")

    def _extract_inbound_message(self, payload: dict[str, Any]) -> dict[str, str] | None:
        entries = payload.get("entry", [])
        if not isinstance(entries, list):
            return None

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            changes = entry.get("changes", [])
            if not isinstance(changes, list):
                continue

            for change in changes:
                if not isinstance(change, dict):
                    continue

                value = change.get("value", {})
                if not isinstance(value, dict):
                    continue

                messages = value.get("messages", [])
                if not isinstance(messages, list):
                    continue

                for message in messages:
                    if not isinstance(message, dict):
                        continue

                    message_type = str(message.get("type") or "")
                    if message_type != "text":
                        return None

                    text_body = message.get("text", {})
                    if not isinstance(text_body, dict):
                        continue

                    body = str(text_body.get("body") or "").strip()
                    sender_phone = str(message.get("from") or "").strip()
                    message_id = str(message.get("id") or "").strip()
                    timestamp = str(message.get("timestamp") or "").strip()

                    if not sender_phone or not body or not message_id:
                        return None

                    return {
                        "sender_phone": sender_phone,
                        "body": body,
                        "message_id": message_id,
                        "timestamp": timestamp,
                        "message_type": message_type,
                    }

        return None

    @staticmethod
    def _extract_twilio_form_value(form_payload: Mapping[str, Any], key: str) -> str:
        value = form_payload.get(key)
        return str(value or "").strip()

    def normalize_twilio_payload(self, payload: Mapping[str, Any]) -> dict[str, str] | None:
        sender_phone = self._extract_twilio_form_value(payload, "From")
        body = self._extract_twilio_form_value(payload, "Body")
        message_id = self._extract_twilio_form_value(payload, "MessageSid")

        if not sender_phone or not body or not message_id:
            return None

        return {
            "sender_phone": sender_phone,
            "body": body,
            "message_id": message_id,
            "timestamp": self._extract_twilio_form_value(payload, "Timestamp"),
            "message_type": "text",
        }

    async def handle_normalized_message(
        self,
        *,
        sender_phone: str,
        body: str,
        message_id: str,
        message_type: str = "text",
        send_outbound: bool = True,
    ) -> dict[str, Any]:
        persistent_memory = getattr(getattr(self.chat_service, "workflow", None), "memory", None)
        if persistent_memory is not None and persistent_memory.has_processed_message(sender_phone, message_id):
            logger.info(
                "whatsapp_webhook_duplicate_detected",
                extra={
                    "event": "whatsapp_webhook_duplicate_detected",
                    "message_id": message_id,
                    "conversation_id": sender_phone,
                    "message_type": message_type,
                },
            )
            return {"status": "duplicate", "processing_result": "already_processed"}

        if message_id in self._seen_message_ids:
            logger.info(
                "whatsapp_webhook_duplicate_detected",
                extra={
                    "event": "whatsapp_webhook_duplicate_detected",
                    "message_id": message_id,
                    "conversation_id": sender_phone,
                    "message_type": message_type,
                },
            )
            return {"status": "duplicate", "processing_result": "already_processed"}

        self._seen_message_ids.add(message_id)
        logger.info(
            "whatsapp_webhook_received",
            extra={
                "event": "whatsapp_webhook_received",
                "message_id": message_id,
                "conversation_id": sender_phone,
                "message_type": message_type,
            },
        )

        try:
            reply = await self.chat_service.chat(
                message=body,
                conversation_id=sender_phone,
                customer_phone=sender_phone,
                message_id=message_id,
            )
        except TypeError:
            reply = await self.chat_service.chat(
                message=body,
                conversation_id=sender_phone,
                message_id=message_id,
            )

        reply_text = self._coerce_reply_text(reply)
        reply_payload_keys = sorted(reply.keys()) if isinstance(reply, dict) else []
        logger.info(
            "whatsapp_twilio_reply_normalized",
            extra={
                "event": "whatsapp_twilio_reply_normalized",
                "message_id": message_id,
                "conversation_id": sender_phone,
                "message_type": message_type,
                "has_reply_text": bool(reply_text),
                "reply_text_length": len(reply_text),
                "chat_result_keys": reply_payload_keys,
            },
        )
        outbound_result: dict[str, Any] = {"status": "skipped"}

        if send_outbound:
            outbound_result = await self.outbound_service.send_text_message(recipient_phone=sender_phone, text=reply_text)

            if outbound_result.get("status") not in {"ok", "skipped"}:
                logger.warning(
                    "whatsapp_outbound_failure",
                    extra={
                        "event": "whatsapp_outbound_failure",
                        "message_id": message_id,
                        "conversation_id": sender_phone,
                        "status": outbound_result.get("status"),
                    },
                )

        return {
            "status": "ok",
            "processing_result": "processed",
            "message_id": message_id,
            "sender_phone": sender_phone,
            "conversation_id": sender_phone,
            "message_type": message_type,
            "reply_text": reply_text,
            "outbound_result": outbound_result,
        }

    async def handle_twilio_webhook(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        event = self.normalize_twilio_payload(payload)

        if event is None:
            logger.warning(
                "twilio_payload_ignored",
                extra={
                    "event": "twilio_payload_ignored",
                    "payload_keys": sorted(payload.keys()),
                },
            )
            return {
                "status": "ignored",
                "processing_result": "unsupported_or_malformed",
                "reply_text": "",
            }

        result = await self.handle_normalized_message(
            sender_phone=event["sender_phone"],
            body=event["body"],
            message_id=event["message_id"],
            message_type=event["message_type"],
            send_outbound=False,
        )

        logger.info(
            "twilio_webhook_service_result",
            extra={
                "event": "twilio_webhook_service_result",
                "status": result.get("status"),
                "processing_result": result.get("processing_result"),
                "has_reply_text": bool(result.get("reply_text")),
                "reply_text_length": len(
                    str(result.get("reply_text") or "")
                ),
            },
        )

        return result

    async def handle_webhook(
        self,
        payload: dict[str, Any],
        signature_header: str | None = None,
        raw_body: bytes | None = None,
    ) -> dict[str, Any]:
        if raw_body is not None and not self._verify_signature(raw_body, signature_header):
            logger.warning(
                "whatsapp_webhook_invalid_signature",
                extra={"event": "whatsapp_webhook_invalid_signature"},
            )
            return {"status": "invalid_signature", "processing_result": "rejected"}

        if not isinstance(payload, dict):
            return {"status": "ignored", "processing_result": "malformed"}

        event = self._extract_inbound_message(payload)
        if event is None:
            return {"status": "ignored", "processing_result": "unsupported_or_malformed"}

        return await self.handle_normalized_message(
            sender_phone=event["sender_phone"],
            body=event["body"],
            message_id=event["message_id"],
            message_type=event["message_type"],
        )
