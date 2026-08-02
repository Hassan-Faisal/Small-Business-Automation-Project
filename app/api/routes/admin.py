from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_auth_token, normalize_email, verify_password
from app.dependencies.admin import require_active_admin
from app.dependencies.database import get_db
from app.models.admin_user import AdminUser
from app.schemas.admin import AdminAuthResponse, AdminLoginRequest, AdminMessageResponse, AdminProfileResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])
auth_router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.ADMIN_COOKIE_NAME,
        value=token,
        max_age=settings.ADMIN_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.ADMIN_COOKIE_SECURE,
        samesite=settings.ADMIN_COOKIE_SAMESITE,
        path="/",
    )


def _profile(admin: AdminUser) -> AdminProfileResponse:
    return AdminProfileResponse.model_validate(admin)


@auth_router.post("/login", response_model=AdminAuthResponse)
def login(payload: AdminLoginRequest, response: Response, db: Session = Depends(get_db)) -> AdminAuthResponse:
    email = normalize_email(payload.email)
    admin = db.scalar(select(AdminUser).where(AdminUser.email == email))
    if admin is None or not admin.is_active or not verify_password(payload.password, admin.hashed_password):
        logger.info("admin_login_failed", extra={"event": "admin_login_failed", "email": email})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    admin.last_login_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(admin)
    except IntegrityError:
        db.rollback()
        logger.exception("admin_login_update_failed", extra={"event": "admin_login_update_failed", "admin_id": admin.id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to complete login.") from None

    token = create_auth_token(admin.id)
    _set_auth_cookie(response, token)
    logger.info("admin_login_success", extra={"event": "admin_login_success", "admin_id": admin.id})
    return AdminAuthResponse(message="Login successful.", admin=_profile(admin))


@auth_router.get("/me", response_model=AdminProfileResponse)
def me(admin: AdminUser = Depends(require_active_admin)) -> AdminProfileResponse:
    return _profile(admin)


@auth_router.post("/logout", response_model=AdminMessageResponse)
def logout(response: Response) -> AdminMessageResponse:
    response.delete_cookie(
        key=settings.ADMIN_COOKIE_NAME,
        httponly=True,
        secure=settings.ADMIN_COOKIE_SECURE,
        samesite=settings.ADMIN_COOKIE_SAMESITE,
        path="/",
    )
    logger.info("admin_logout", extra={"event": "admin_logout"})
    return AdminMessageResponse(message="Logout successful.")


@router.get("/protected-check", response_model=AdminProfileResponse)
def protected_check(admin: AdminUser = Depends(require_active_admin)) -> AdminProfileResponse:
    return _profile(admin)