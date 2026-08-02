from __future__ import annotations

import logging

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import AuthenticationError, decode_auth_token
from app.models.admin_user import AdminUser

logger = logging.getLogger(__name__)


def get_current_admin(
    auth_token: str | None = Cookie(default=None, alias=settings.ADMIN_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> AdminUser:
    if not auth_token:
        logger.info("admin_auth_blocked_missing_cookie", extra={"event": "admin_auth_blocked_missing_cookie"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        payload = decode_auth_token(auth_token)
        admin_id = int(payload["sub"])
    except (AuthenticationError, ValueError, TypeError):
        logger.info("admin_auth_invalid_or_expired", extra={"event": "admin_auth_invalid_or_expired"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.") from None

    admin = db.scalar(select(AdminUser).where(AdminUser.id == admin_id))
    if admin is None:
        logger.info("admin_auth_invalid_user", extra={"event": "admin_auth_invalid_user"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    if not admin.is_active:
        logger.info("admin_auth_blocked_inactive", extra={"event": "admin_auth_blocked_inactive", "admin_id": admin.id})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin account is inactive.")
    return admin


def require_active_admin(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    return admin