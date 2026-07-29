from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.services.whatsapp_transport import WhatsAppWebhookService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/twilio", tags=["Twilio WhatsApp"])


def _get_webhook_service(request: Request) -> WhatsAppWebhookService:
    webhook_service = getattr(request.app.state, "twilio_webhook_service", None)
    if webhook_service is not None:
        return webhook_service

    chat_service = getattr(request.app.state, "chat_service", None)
    if chat_service is None or not hasattr(chat_service, "chat"):
        raise RuntimeError("Chat service unavailable")

    outbound_service = getattr(request.app.state, "whatsapp_outbound_service", None)
    webhook_service = WhatsAppWebhookService(chat_service=chat_service, outbound_service=outbound_service)
    request.app.state.twilio_webhook_service = webhook_service
    return webhook_service


def _trusted_request_url(request: Request) -> str:
    # Twilio signs the externally visible URL. We intentionally avoid trusting forwarded
    # headers unless the deployment has already normalized them, because proxy headers can
    # be spoofed in direct requests. If a reverse proxy or tunnel rewrites the public URL,
    # configure the app/proxy so request.url reflects that canonical address.
    if getattr(settings, "TWILIO_TRUST_FORWARDED_HEADERS", False):
        forwarded_proto = request.headers.get("x-forwarded-proto")
        forwarded_host = request.headers.get("x-forwarded-host")
        if forwarded_proto or forwarded_host:
            parts = urlsplit(str(request.url))
            scheme = forwarded_proto or parts.scheme
            netloc = forwarded_host or parts.netloc
            return urlunsplit((scheme, netloc, parts.path, parts.query, parts.fragment))
    return str(request.url)


def _get_twilio_request_validator() -> Any:
    try:
        from twilio.request_validator import RequestValidator
    except ImportError as exc:  # pragma: no cover - depends on deployment packaging
        raise RuntimeError(
            "Twilio signature verification is enabled but the twilio package is not installed."
        ) from exc
    return RequestValidator


def _validate_twilio_signature(request: Request, form_payload: dict[str, str]) -> bool:
    if not getattr(settings, "TWILIO_SIGNATURE_VERIFICATION_ENABLED", True):
        return True

    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        return False

    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        return False

    request_validator = _get_twilio_request_validator()
    validator = request_validator(auth_token)
    return bool(validator.validate(_trusted_request_url(request), form_payload, signature))


def _empty_twiml() -> Response:
    return Response(content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type='application/xml')


def _build_twiml(reply_text: str | None) -> Response:
    if not reply_text:
        return _empty_twiml()

    try:
        from twilio.twiml.messaging_response import MessagingResponse
    except ImportError as exc:  # pragma: no cover - depends on deployment packaging
        raise RuntimeError("Twilio TwiML generation requires the twilio package.") from exc

    response = MessagingResponse()
    response.message(reply_text)
    return Response(content=str(response), media_type="application/xml")


@router.post("")
async def inbound_twilio_webhook(request: Request) -> Response:
    raw_body = await request.body()
    form_payload = dict(parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True))

    if not _validate_twilio_signature(request, form_payload):
        logger.warning(
            "twilio_webhook_invalid_signature",
            extra={"event": "twilio_webhook_invalid_signature"},
        )
        return _empty_twiml()

    try:
        webhook_service = _get_webhook_service(request)
    except RuntimeError:
        logger.warning(
            "twilio_webhook_chat_service_unavailable",
            extra={"event": "twilio_webhook_chat_service_unavailable"},
        )
        return _empty_twiml()

    result = await webhook_service.handle_twilio_webhook(form_payload)

    reply_text = str(result.get("reply_text") or "").strip()

    logger.info(
        "twilio_route_reply_result",
        extra={
            "event": "twilio_route_reply_result",
            "status": result.get("status"),
            "processing_result": result.get("processing_result"),
            "has_reply_text": bool(reply_text),
            "reply_text_length": len(reply_text),
            "result_keys": sorted(result.keys()),
        },
    )

    logger.info(
        "Processed Twilio WhatsApp webhook event",
        extra={
            "event": "twilio_webhook_processed",
            "message_id": result.get("message_id"),
            "conversation_id": result.get("conversation_id"),
            "message_type": result.get("message_type"),
            "processing_result": result.get("processing_result"),
        },
    )

    if result.get("status") in {"duplicate", "ignored"}:
        return _empty_twiml()

    if not reply_text:
        logger.warning(
            "twilio_route_empty_reply",
            extra={
                "event": "twilio_route_empty_reply",
                "message_id": result.get("message_id"),
                "conversation_id": result.get("conversation_id"),
            },
        )
        return _empty_twiml()

    twiml_response = _build_twiml(reply_text)

    logger.info(
        "twilio_route_twiml_created",
        extra={
            "event": "twilio_route_twiml_created",
            "reply_text_length": len(reply_text),
        },
    )

    return twiml_response
