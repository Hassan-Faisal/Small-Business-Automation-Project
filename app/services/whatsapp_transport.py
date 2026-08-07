from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import setup_logger
from app.services.meta_graph_errors import classify_meta_failure, extract_meta_graph_error, redact_meta_error_details, safe_exception_details

logger = setup_logger(__name__)
DEFAULT_REPLY = "I can help with today's menu, your cart, orders, subscriptions, and delivery policies. Try 'today menu' or 'view cart'."


class WhatsAppOutboundService:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))

    async def send_text_message(self, recipient_phone: str, text: str) -> dict[str, Any]:
        return await self._send_payload(recipient_phone, {"messaging_product": "whatsapp", "to": recipient_phone, "type": "text", "text": {"body": text}})

    async def send_template_message(self, recipient_phone: str, template_name: str, language_code: str) -> dict[str, Any]:
        return await self._send_payload(recipient_phone, {"messaging_product": "whatsapp", "to": recipient_phone, "type": "template", "template": {"name": template_name, "language": {"code": language_code}}})

    async def _send_payload(self, recipient_phone: str, payload: dict[str, Any]) -> dict[str, Any]:
        access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", None)
        phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
        api_version = getattr(settings, "WHATSAPP_API_VERSION", "v20.0")
        if not access_token or not phone_number_id:
            return {"status": "skipped"}
        reply_length = len(str(payload.get("text", {}).get("body", ""))) if isinstance(payload.get("text"), Mapping) else 0
        log_context = {"event": "meta_outbound_request", "destination_phone_suffix": recipient_phone[-4:], "reply_length": reply_length, "http_status": None, "success": False, "provider_message_id": None, "error_type": None, "error_code": None, "error_error_subcode": None, "error_message": None, "error_data_details": None, "fbtrace_id": None, "exception_type": None, "exception_message": None, "safe_failure_category": None}
        logger.info("meta_outbound_boundary_enter", extra={"event": "meta_outbound_boundary_enter", "destination_phone_suffix": recipient_phone[-4:], "reply_length": reply_length})
        try:
            response = await self.client.post(f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages", headers={"Authorization": f"Bearer {access_token}"}, json=payload)
            response.raise_for_status()
            data = response.json()
            messages = data.get("messages") if isinstance(data, Mapping) else None
            provider_message_id = messages[0].get("id") if isinstance(messages, list) and messages and isinstance(messages[0], Mapping) else None
            log_context.update({"http_status": response.status_code, "success": True, "provider_message_id": provider_message_id})
            logger.info("meta_outbound_request", extra=log_context)
            return {"status": "ok", "data": data}
        except httpx.TimeoutException as exc:
            log_context["safe_failure_category"] = "transport_error"
            logger.info("meta_outbound_request", extra=log_context)
            return {"status": "timeout", "detail": str(exc)}
        except httpx.HTTPStatusError as exc:
            error_details = None
            try:
                error_details = extract_meta_graph_error(exc.response.json(), status_code=exc.response.status_code)
            except (ValueError, TypeError):
                pass
            safe_details = redact_meta_error_details(error_details, (access_token, getattr(settings, "META_APP_SECRET", ""), getattr(settings, "WHATSAPP_VERIFY_TOKEN", "")))
            log_context.update({"http_status": exc.response.status_code, "error_type": safe_details.get("type"), "error_code": safe_details.get("code"), "error_error_subcode": safe_details.get("error_subcode"), "error_message": safe_details.get("message"), "error_data_details": safe_details.get("error_data_details"), "fbtrace_id": safe_details.get("fbtrace_id"), "safe_failure_category": classify_meta_failure(error_details, status_code=exc.response.status_code)})
            logger.info("meta_outbound_request", extra=log_context)
            return {"status": "error", "status_code": exc.response.status_code, "detail": exc.response.text, "error_details": error_details}
        except httpx.HTTPError as exc:
            log_context["safe_failure_category"] = "transport_error"
            logger.info("meta_outbound_request", extra=log_context)
            return {"status": "error", "detail": str(exc), "transport_error": True}
        except Exception as exc:
            exception_details = safe_exception_details(exc, (access_token, getattr(settings, "META_APP_SECRET", ""), getattr(settings, "WHATSAPP_VERIFY_TOKEN", "")))
            log_context.update(exception_details)
            log_context["safe_failure_category"] = "transport_exception"
            logger.exception("meta_outbound_request", extra=log_context)
            return {"status": "error", "transport_error": True, **exception_details}


class WhatsAppWebhookService:
    def __init__(self, chat_service: Any, outbound_service: WhatsAppOutboundService | None = None, signature_secret: str | None = None, verify_token: str | None = None) -> None:
        self.chat_service = chat_service
        self.outbound_service = outbound_service or WhatsAppOutboundService()
        self.signature_secret = signature_secret or getattr(settings, "WHATSAPP_WEBHOOK_SECRET", None)
        self.verify_token = verify_token or getattr(settings, "WHATSAPP_VERIFY_TOKEN", None)
        self._seen_message_ids: set[str] = set()

    def verify_webhook(self, hub_mode: str | None, hub_verify_token: str | None, hub_challenge: str | None) -> tuple[int, str]:
        return (200, hub_challenge or "") if hub_mode == "subscribe" and hub_verify_token == self.verify_token else (403, "Verification failed")

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
                    nested = WhatsAppWebhookService._coerce_reply_text(value)
                    if nested:
                        return nested
        for attribute in ("response", "content"):
            value = getattr(reply, attribute, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _verify_signature(self, payload: bytes, signature_header: str | None) -> bool:
        if not self.signature_secret or not signature_header:
            return True
        expected = hmac.new(self.signature_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature_header, f"sha256={expected}")

    @staticmethod
    def _extract_twilio_form_value(form_payload: Mapping[str, Any], key: str) -> str:
        return str(form_payload.get(key) or "").strip()

    def normalize_twilio_payload(self, payload: Mapping[str, Any]) -> dict[str, str] | None:
        sender_phone = self._extract_twilio_form_value(payload, "From")
        body = self._extract_twilio_form_value(payload, "Body")
        message_id = self._extract_twilio_form_value(payload, "MessageSid")
        if not sender_phone or not body or not message_id:
            return None
        return {"sender_phone": sender_phone, "body": body, "message_id": message_id, "timestamp": self._extract_twilio_form_value(payload, "Timestamp"), "message_type": "text"}

    def _extract_inbound_message(self, payload: Mapping[str, Any]) -> dict[str, str] | None:
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
                    if not isinstance(message, dict) or str(message.get("type") or "") != "text":
                        continue
                    text_body = message.get("text", {})
                    if not isinstance(text_body, dict):
                        continue
                    body = str(text_body.get("body") or "").strip()
                    sender_phone = str(message.get("from") or "").strip()
                    message_id = str(message.get("id") or "").strip()
                    if sender_phone and body and message_id:
                        return {"sender_phone": sender_phone, "body": body, "message_id": message_id, "timestamp": str(message.get("timestamp") or ""), "message_type": "text"}
        return None
    async def handle_normalized_message(self, *, sender_phone: str, body: str, message_id: str, message_type: str = "text", send_outbound: bool = True) -> dict[str, Any]:
        persistent_memory = getattr(getattr(self.chat_service, "workflow", None), "memory", None)
        if persistent_memory is not None and persistent_memory.has_processed_message(sender_phone, message_id):
            return {"status": "duplicate", "processing_result": "already_processed"}
        if message_id in self._seen_message_ids:
            return {"status": "duplicate", "processing_result": "already_processed"}
        self._seen_message_ids.add(message_id)
        try:
            reply = await self.chat_service.chat(message=body, conversation_id=sender_phone, customer_phone=sender_phone, message_id=message_id)
        except TypeError:
            reply = await self.chat_service.chat(message=body, conversation_id=sender_phone, message_id=message_id)
        reply_text = self._coerce_reply_text(reply) or DEFAULT_REPLY
        outbound_result: dict[str, Any] = {"status": "skipped"}
        if send_outbound:
            outbound_result = await self.outbound_service.send_text_message(recipient_phone=sender_phone, text=reply_text)
        return {"status": "ok", "processing_result": "processed", "message_id": message_id, "sender_phone": sender_phone, "conversation_id": sender_phone, "message_type": message_type, "reply_text": reply_text, "outbound_result": outbound_result}

    async def handle_twilio_webhook(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        event = self.normalize_twilio_payload(payload)
        if event is None:
            return {"status": "ignored", "processing_result": "unsupported_or_malformed", "reply_text": ""}
        return await self.handle_normalized_message(sender_phone=event["sender_phone"], body=event["body"], message_id=event["message_id"], message_type=event["message_type"], send_outbound=False)

    async def handle_webhook(self, payload: dict[str, Any], signature_header: str | None = None, raw_body: bytes | None = None) -> dict[str, Any]:
        if raw_body is not None and not self._verify_signature(raw_body, signature_header):
            return {"status": "invalid_signature", "processing_result": "rejected"}
        if not isinstance(payload, dict):
            return {"status": "ignored", "processing_result": "malformed"}
        event = self._extract_inbound_message(payload)
        if event is None:
            return {"status": "ignored", "processing_result": "unsupported_or_malformed"}
        return await self.handle_normalized_message(sender_phone=event["sender_phone"], body=event["body"], message_id=event["message_id"], message_type=event["message_type"])