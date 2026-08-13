from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.dependencies.admin import require_active_admin
from app.models.admin_user import AdminUser
from app.schemas.meta import (
    MetaEmbeddedSignupCompletionRequest,
    MetaEmbeddedSignupCompletionResponse,
    MetaEmbeddedSignupConfigResponse,
)
from app.services.meta_embedded_signup import MetaEmbeddedSignupError, MetaEmbeddedSignupService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/meta/embedded-signup", tags=["admin-meta"])


@router.get("/config", response_model=MetaEmbeddedSignupConfigResponse)
def embedded_signup_config(_: AdminUser = Depends(require_active_admin)) -> MetaEmbeddedSignupConfigResponse:
    if not settings.META_APP_ID.strip() or not settings.META_EMBEDDED_SIGNUP_CONFIG_ID.strip():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Meta Embedded Signup is not configured.")
    return MetaEmbeddedSignupConfigResponse(app_id=settings.META_APP_ID.strip(), config_id=settings.META_EMBEDDED_SIGNUP_CONFIG_ID.strip())


@router.post("/complete", response_model=MetaEmbeddedSignupCompletionResponse)
def complete_embedded_signup(
    payload: MetaEmbeddedSignupCompletionRequest,
    _: AdminUser = Depends(require_active_admin),
) -> MetaEmbeddedSignupCompletionResponse:
    try:
        exchanged = MetaEmbeddedSignupService().exchange_code(payload.code)
    except MetaEmbeddedSignupError as exc:
        logger.warning(
            "meta_embedded_signup_completion_failed",
            extra={"event": "meta_embedded_signup_completion_failed", "waba_id": payload.waba_id, "phone_number_id": payload.phone_number_id},
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    logger.info(
        "meta_embedded_signup_completed",
        extra={"event": "meta_embedded_signup_completed", "waba_id": payload.waba_id, "phone_number_id": payload.phone_number_id, "access_token_exchanged": exchanged},
    )
    return MetaEmbeddedSignupCompletionResponse(status="completed", waba_id=payload.waba_id, phone_number_id=payload.phone_number_id, access_token_exchanged=exchanged)
