from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.services.chat_service import ChatService
from app.services.whatsapp_service import WhatsAppWebhookService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhook",
    tags=["WhatsApp"],
)


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    """Verify the webhook with Meta."""

    service = WhatsAppWebhookService(chat_service=None)
    status_code, response_text = service.verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    if status_code == status.HTTP_200_OK:
        return PlainTextResponse(content=response_text, status_code=status_code)

    raise HTTPException(status_code=status_code, detail=response_text)


@router.post("")
async def receive_webhook(request: Request) -> dict[str, Any]:
    """Receive and process WhatsApp webhook events."""

    raw_body = await request.body()
    payload = await request.json()

    chat_service = getattr(
        request.app.state,
        "chat_service",
        None,
    )

    if not isinstance(chat_service, ChatService):
        logger.warning(
            "whatsapp_webhook_chat_service_unavailable",
            extra={"event": "whatsapp_webhook_chat_service_unavailable"},
        )
        return {"status": "ok"}

    signature_header = request.headers.get(
        "x-hub-signature-256"
    )

    service = WhatsAppWebhookService(
        chat_service=chat_service
    )

    return await service.handle_webhook(
        payload=payload,
        signature_header=signature_header,
        raw_body=raw_body,
    )
