from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.config import settings
from app.services.whatsapp_transport import WhatsAppOutboundService, WhatsAppWebhookService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])


def _get_chat_service(request: Request) -> Any:
    chat_service = getattr(request.app.state, "chat_service", None)
    if chat_service is None:
        raise HTTPException(status_code=500, detail="Chat service unavailable")
    return chat_service


def _get_webhook_service(request: Request) -> WhatsAppWebhookService:
    webhook_service = getattr(request.app.state, "whatsapp_webhook_service", None)
    if webhook_service is not None:
        return webhook_service

    chat_service = _get_chat_service(request)
    outbound_service = getattr(request.app.state, "whatsapp_outbound_service", None)
    if outbound_service is None:
        outbound_service = WhatsAppOutboundService()

    webhook_service = WhatsAppWebhookService(chat_service=chat_service, outbound_service=outbound_service)
    request.app.state.whatsapp_webhook_service = webhook_service
    return webhook_service


@router.get("")
async def verify_webhook(
    request: Request,
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", None)
    if hub_mode != "subscribe" or hub_verify_token != verify_token:
        return JSONResponse(status_code=403, content={"detail": "Verification failed"})

    return PlainTextResponse(hub_challenge or "", status_code=200)


@router.post("")
async def inbound_webhook(request: Request):
    raw_body = await request.body()

    try:
        payload = await request.json()
    except ValueError:
        payload = {}

    webhook_service = _get_webhook_service(request)
    result = await webhook_service.handle_webhook(
        payload=payload if isinstance(payload, dict) else {},
        signature_header=request.headers.get("X-Hub-Signature-256"),
        raw_body=raw_body,
    )

    logger.info(
        "Processed WhatsApp webhook event",
        extra={
            "message_id": result.get("message_id"),
            "conversation_id": result.get("conversation_id"),
            "message_type": result.get("message_type"),
            "processing_result": result.get("processing_result"),
        },
    )
    return JSONResponse(status_code=200, content={"status": result.get("status", "ok")})