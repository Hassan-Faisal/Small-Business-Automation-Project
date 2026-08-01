from __future__ import annotations

import logging
import unicodedata
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.services.whatsapp_transport import WhatsAppWebhookService

logger = logging.getLogger(__name__)
MAX_REPLY_LENGTH = 1500
_REPLY_CONTINUATION = "\n\nSome details were shortened. Ask for breakfast, lunch, or dinner separately."


def _limit_reply_text(reply_text: str) -> str:
    original_length = len(reply_text)
    logger.info(
        "twilio_reply_length_checked",
        extra={
            "event": "twilio_reply_length_checked",
            "original_reply_length": original_length,
            "max_reply_length": MAX_REPLY_LENGTH,
        },
    )
    if original_length <= MAX_REPLY_LENGTH:
        return reply_text

    available = MAX_REPLY_LENGTH - len(_REPLY_CONTINUATION)
    shortened = reply_text[:available]
    word_break = shortened.rfind(" ")
    if word_break > 0:
        shortened = shortened[:word_break]
    while shortened and unicodedata.combining(shortened[-1]):
        shortened = shortened[:-1]
    return shortened.rstrip(" \t\r\n,;:-") + _REPLY_CONTINUATION

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


def _forwarded_request_url(request: Request) -> str | None:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if not forwarded_proto and not forwarded_host:
        return None

    parts = urlsplit(str(request.url))
    scheme = forwarded_proto or parts.scheme
    netloc = forwarded_host or parts.netloc
    return urlunsplit((scheme, netloc, parts.path, parts.query, parts.fragment))


def _trusted_request_urls(request: Request) -> list[str]:
    direct_url = str(request.url)
    if not getattr(settings, "TWILIO_TRUST_FORWARDED_HEADERS", False):
        return [direct_url]

    urls = [direct_url]
    forwarded_url = _forwarded_request_url(request)
    if forwarded_url and forwarded_url not in urls:
        urls.insert(0, forwarded_url)
    return urls


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
    return any(
        bool(validator.validate(candidate_url, form_payload, signature))
        for candidate_url in _trusted_request_urls(request)
    )


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

    reply_text = _limit_reply_text(reply_text)
    twiml_response = _build_twiml(reply_text)

    logger.info(
        "twilio_route_twiml_created",
        extra={
            "event": "twilio_route_twiml_created",
            "reply_text_length": len(reply_text),
        },
    )

    return twiml_response
