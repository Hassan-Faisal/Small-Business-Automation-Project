from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.responses import Response

from app.core.config import settings
from app.services.meta_webhook_adapter import MetaWebhookAdapter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/meta", tags=["Meta WhatsApp"])


def _adapter(request: Request) -> MetaWebhookAdapter:
    adapter = getattr(request.app.state, "meta_webhook_adapter", None)
    if adapter is None:
        adapter = MetaWebhookAdapter()
        request.app.state.meta_webhook_adapter = adapter
    return adapter


@router.get("")
async def verify_meta_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> Response:
    expected = settings.WHATSAPP_VERIFY_TOKEN.strip()
    if hub_mode != "subscribe" or not expected or not hub_verify_token or not hmac_compare(hub_verify_token, expected):
        return JSONResponse(status_code=403, content={"detail": "Meta webhook verification failed"})
    return PlainTextResponse(hub_challenge or "", status_code=200)


def hmac_compare(left: str, right: str) -> bool:
    import hmac
    return hmac.compare_digest(left, right)


@router.post("")
async def receive_meta_webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()
    adapter = _adapter(request)
    if not adapter.verify_signature(raw_body, request.headers.get("X-Hub-Signature-256")):
        return JSONResponse(status_code=403, content={"detail": "Meta webhook signature invalid"})
    payload = adapter.safe_json(raw_body)
    if payload is None:
        logger.info("Ignored malformed Meta WhatsApp webhook")
        return JSONResponse(status_code=200, content={"status": "ignored"})
    result = adapter.parse(payload)
    if result.event is not None:
        logger.info("Received Meta WhatsApp message", extra={"whatsapp_business_account_id": result.event.whatsapp_business_account_id, "phone_number_id": result.event.phone_number_id, "sender_phone": result.event.sender_phone, "message_id": result.event.message_id, "timestamp": result.event.timestamp, "message_type": result.event.message_type, "text_body_length": len(result.event.text_body)})
    else:
        logger.info("Ignored Meta WhatsApp webhook", extra={"reason": result.reason})
    return JSONResponse(status_code=200, content={"status": result.status})
