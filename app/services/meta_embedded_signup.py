from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.services.meta_graph_errors import extract_meta_graph_error, redact_meta_error_details

logger = logging.getLogger(__name__)


class MetaEmbeddedSignupError(RuntimeError):
    """Raised when Meta cannot exchange an Embedded Signup authorization code."""


class MetaEmbeddedSignupService:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0))

    def exchange_code(self, code: str) -> bool:
        if not settings.META_APP_ID.strip() or not settings.META_APP_SECRET.strip():
            raise MetaEmbeddedSignupError("Meta app credentials are not configured.")

        url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION.strip()}/oauth/access_token"
        try:
            response = self.client.get(
                url,
                params={
                    "client_id": settings.META_APP_ID.strip(),
                    "client_secret": settings.META_APP_SECRET.strip(),
                    "code": code,
                },
            )
            payload: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MetaEmbeddedSignupError("Meta authorization code exchange failed.") from exc

        if response.is_error or not payload.get("access_token"):
            details = extract_meta_graph_error(payload, status_code=response.status_code)
            safe_details = redact_meta_error_details(
                details or {"message": "Meta authorization code exchange failed."},
                (settings.META_APP_SECRET, code),
            )
            logger.warning(
                "meta_embedded_signup_code_exchange_failed",
                extra={"event": "meta_embedded_signup_code_exchange_failed", "details": safe_details},
            )
            raise MetaEmbeddedSignupError("Meta authorization code exchange failed.")

        logger.info("meta_embedded_signup_code_exchanged", extra={"event": "meta_embedded_signup_code_exchanged"})
        return True
