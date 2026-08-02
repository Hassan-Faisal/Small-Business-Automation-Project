from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.routes.admin import auth_router, router as admin_router
from app.core import security
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_auth_token, hash_password, verify_password
from app.models.admin_user import AdminUser


def build_admin_app(db_session, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr(settings, "ADMIN_AUTH_SECRET", "test-admin-secret-that-is-long-enough")
    monkeypatch.setattr(settings, "ADMIN_COOKIE_SECURE", False)
    app = FastAPI()
    app.include_router(admin_router)
    app.include_router(auth_router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return app


def create_admin(db_session, *, email: str = "owner@example.com", is_active: bool = True) -> AdminUser:
    admin = AdminUser(
        full_name="Business Owner",
        email=email,
        hashed_password=hash_password("StrongPassword1"),
        is_active=is_active,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def test_admin_model_hashes_and_verifies_password(db_session) -> None:
    admin = create_admin(db_session)

    assert admin.hashed_password != "StrongPassword1"
    assert verify_password("StrongPassword1", admin.hashed_password) is True
    assert verify_password("WrongPassword1", admin.hashed_password) is False
    assert admin.role == "owner"
    assert admin.is_active is True


def test_duplicate_normalized_email_is_rejected(db_session) -> None:
    create_admin(db_session, email="owner@example.com")
    duplicate = AdminUser(
        full_name="Second Owner",
        email="OWNER@EXAMPLE.COM",
        hashed_password=hash_password("AnotherStrong1"),
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_login_me_protected_check_and_logout(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    admin = create_admin(db_session)
    app = build_admin_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login = client.post("/admin/auth/login", json={"email": " OWNER@EXAMPLE.COM ", "password": "StrongPassword1"})
        assert login.status_code == 200
        assert login.json()["admin"]["id"] == admin.id
        assert "hashed_password" not in login.json()
        assert login.cookies.get(settings.ADMIN_COOKIE_NAME)

        profile = client.get("/admin/auth/me")
        assert profile.status_code == 200
        assert profile.json()["email"] == "owner@example.com"
        assert "hashed_password" not in profile.json()

        protected = client.get("/admin/protected-check")
        assert protected.status_code == 200
        assert protected.json()["id"] == admin.id

        logout = client.post("/admin/auth/logout")
        assert logout.status_code == 200
        assert client.get("/admin/auth/me").status_code == 401
        assert client.get("/admin/protected-check").status_code == 401


def test_authentication_is_required_and_inactive_admin_cannot_login(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    inactive = create_admin(db_session, email="inactive@example.com", is_active=False)
    app = build_admin_app(db_session, monkeypatch)

    with TestClient(app) as client:
        assert client.get("/admin/auth/me").status_code == 401
        login = client.post("/admin/auth/login", json={"email": inactive.email, "password": "StrongPassword1"})
        assert login.status_code == 401
        assert login.json()["detail"] == "Invalid email or password."

        client.cookies.set(settings.ADMIN_COOKIE_NAME, create_auth_token(inactive.id))
        assert client.get("/admin/protected-check").status_code == 403


def test_tampered_and_expired_authentication_is_rejected(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    admin = create_admin(db_session)
    app = build_admin_app(db_session, monkeypatch)

    with TestClient(app) as client:
        token = create_auth_token(admin.id)
        client.cookies.set(settings.ADMIN_COOKIE_NAME, token[:-1] + ("A" if token[-1] != "A" else "B"))
        assert client.get("/admin/auth/me").status_code == 401

        current_time = security.time.time()
        expired_token = create_auth_token(admin.id)
        monkeypatch.setattr(security.time, "time", lambda: current_time + settings.ADMIN_TOKEN_EXPIRE_MINUTES * 60 + 1)
        client.cookies.set(settings.ADMIN_COOKIE_NAME, expired_token)
        assert client.get("/admin/auth/me").status_code == 401


def test_missing_auth_secret_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_AUTH_SECRET", "")
    with pytest.raises(RuntimeError, match="ADMIN_AUTH_SECRET"):
        create_auth_token(1)