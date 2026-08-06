from __future__ import annotations

import hmac
import logging
from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.responses import Response

from app.core.config import settings
from app.services.meta_message_processing_service import MetaMessageProcessingService
from app.services.meta_webhook_adapter import MetaWebhookAdapter
from app.services.whatsapp_outbound_provider import build_whatsapp_outbound_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/meta", tags=["Meta WhatsApp"])


def _adapter(request: Request) -> MetaWebhookAdapter:
    adapter = getattr(request.app.state, "meta_webhook_adapter", None)
    if adapter is None:
        adapter = MetaWebhookAdapter()
        request.app.state.meta_webhook_adapter = adapter
    return adapter


def _processor(request: Request) -> MetaMessageProcessingService | None:
    processor = getattr(request.app.state, "meta_message_processing_service", None)
    if processor is not None:
        return processor
    chat_service = getattr(request.app.state, "chat_service", None)
    if chat_service is None or not hasattr(chat_service, "chat"):
        return None
    processor = MetaMessageProcessingService(chat_service=chat_service, provider=build_whatsapp_outbound_provider())
    request.app.state.meta_message_processing_service = processor
    return processor


@router.get("")
async def verify_meta_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> Response:
    expected = settings.WHATSAPP_VERIFY_TOKEN.strip()
    if hub_mode != "subscribe" or not expected or not hub_verify_token or not hmac.compare_digest(hub_verify_token, expected):
        return JSONResponse(status_code=403, content={"detail": "Meta webhook verification failed"})
    return PlainTextResponse(hub_challenge or "", status_code=200)


@router.post("")
async def receive_meta_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")
    adapter = _adapter(request)
    logger.info("meta_webhook_request_received", extra={"event": "meta_webhook_request_received", "body_length": len(raw_body), "signature_header_present": bool(signature_header), "signature_verification_enabled": settings.META_SIGNATURE_VERIFICATION_ENABLED})
    signature_valid = adapter.verify_signature(raw_body, signature_header)
    logger.info("meta_webhook_signature_result", extra={"event": "meta_webhook_signature_result", "valid": signature_valid})
    if not signature_valid:
        return JSONResponse(status_code=403, content={"detail": "Meta webhook signature invalid"})
    payload = adapter.safe_json(raw_body)
    if payload is None:
        logger.info("meta_webhook_payload_summary", extra={"event": "meta_webhook_payload_summary", "entry_count": 0, "change_count": 0, "message_count": 0, "status_count": 0, "ignored_count": 1})
        return JSONResponse(status_code=200, content={"status": "ignored"})
    result = adapter.parse(payload)
    summary = result.summary
    logger.info("meta_webhook_payload_summary", extra={"event": "meta_webhook_payload_summary", "entry_count": summary.entry_count, "change_count": summary.change_count, "message_count": summary.message_count, "status_count": summary.status_count, "ignored_count": summary.ignored_count})
    if result.events:
        processor = _processor(request)
        if processor is None:
            for event in result.events:
                logger.warning("meta_message_processing_result", extra={"event": "meta_message_processing_result", "message_id": event.message_id, "conversation_id": None, "result": "chat_service_unavailable", "reply_length": 0, "duration_ms": 0})
        else:
            for event in result.events:
                background_tasks.add_task(processor.process, event)
    return JSONResponse(status_code=200, content={"status": result.status})
