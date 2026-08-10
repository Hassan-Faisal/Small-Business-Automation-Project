from __future__ import annotations

import pytest
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


def test_admin_frontend_origins_are_explicit_and_credentials_are_enabled() -> None:
    cors = next(middleware for middleware in app.user_middleware if middleware.cls is CORSMiddleware)

    assert cors.kwargs["allow_origins"] == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert cors.kwargs["allow_credentials"] is True
    assert "*" not in cors.kwargs["allow_origins"]
    assert set(cors.kwargs["allow_methods"]) == {"GET", "POST", "PATCH", "DELETE", "OPTIONS"}
    assert set(cors.kwargs["allow_headers"]) == {"Accept", "Content-Type"}


def test_admin_frontend_origins_parse_and_reject_wildcard() -> None:
    configured = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/tiffin_ai",
        ADMIN_FRONTEND_ORIGINS="https://admin.example.com, https://owner.example.com",
    )
    assert configured.admin_frontend_origins == ["https://admin.example.com", "https://owner.example.com"]

    with pytest.raises(ValidationError, match="explicit origins"):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/tiffin_ai",
            ADMIN_FRONTEND_ORIGINS="*",
        )


@pytest.mark.parametrize("samesite", ["lax", "strict", "none", "LAX", "None"])
def test_admin_cookie_samesite_accepts_supported_values(samesite: str) -> None:
    configured = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/tiffin_ai",
        ADMIN_COOKIE_SAMESITE=samesite,
    )
    assert configured.ADMIN_COOKIE_SAMESITE == samesite.lower()


def test_admin_cookie_samesite_rejects_invalid_value() -> None:
    with pytest.raises(ValidationError, match="lax, strict, or none"):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/tiffin_ai",
            ADMIN_COOKIE_SAMESITE="cross-site",
        )
