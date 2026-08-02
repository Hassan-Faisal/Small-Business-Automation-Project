from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import bcrypt

from app.core.config import settings


class AuthenticationError(ValueError):
    """Raised when an admin authentication token is invalid or expired."""


def normalize_email(email: str) -> str:
    return " ".join(email.strip().lower().split())


def validate_password_strength(password: str) -> None:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long.")
    if not any(char.isupper() for char in password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not any(char.islower() for char in password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not any(char.isdigit() for char in password):
        raise ValueError("Password must contain at least one digit.")


def hash_password(password: str) -> str:
    validate_password_strength(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _auth_secret() -> bytes:
    secret = str(settings.ADMIN_AUTH_SECRET or "").strip()
    if not secret:
        raise RuntimeError("ADMIN_AUTH_SECRET is required before admin authentication can be used.")
    return secret.encode("utf-8")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_auth_token(admin_id: int) -> str:
    now = int(time.time())
    payload = {"sub": str(admin_id), "iat": now, "exp": now + settings.ADMIN_TOKEN_EXPIRE_MINUTES * 60}
    encoded_payload = _encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _encode(hmac.new(_auth_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded_payload}.{signature}"


def decode_auth_token(token: str) -> dict[str, Any]:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected_signature = _encode(hmac.new(_auth_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(encoded_signature, expected_signature):
            raise AuthenticationError("Invalid authentication token.")
        payload = json.loads(_decode(encoded_payload))
        if not isinstance(payload, dict) or int(payload["exp"]) <= int(time.time()):
            raise AuthenticationError("Authentication token expired.")
        if int(payload["sub"]) <= 0:
            raise AuthenticationError("Invalid authentication subject.")
        return payload
    except (AuthenticationError, RuntimeError):
        raise
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeError) as exc:
        raise AuthenticationError("Invalid authentication token.") from exc