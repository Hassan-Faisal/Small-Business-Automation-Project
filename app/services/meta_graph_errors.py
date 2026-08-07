from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

_SAFE_KEYS = {"type", "code", "error_subcode", "message", "fbtrace_id"}


def extract_meta_graph_error(payload: Any, *, status_code: int | None = None) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    error = payload.get("error")
    if not isinstance(error, Mapping):
        return None
    details: dict[str, Any] = {}
    if status_code is not None:
        details["http_status"] = status_code
    for key in _SAFE_KEYS:
        value = error.get(key)
        if isinstance(value, (str, int)) and str(value):
            details[key] = value
    error_data = error.get("error_data")
    if isinstance(error_data, Mapping):
        value = error_data.get("details")
        if isinstance(value, str) and value:
            details["error_data_details"] = value
    return details or None


def classify_meta_failure(details: Mapping[str, Any] | None, *, status_code: int | None = None, transport: bool = False) -> str:
    if transport:
        return "transport_error"
    code = details.get("code") if details else None
    subcode = details.get("error_subcode") if details else None
    message = str(details.get("message", "")).lower() if details else ""
    if status_code == 429 or code in {4, 80007, 130429}:
        return "rate_limit_error"
    if subcode == 131047 or "24 hour" in message or "conversation window" in message:
        return "conversation_window_error"
    if status_code == 401 or code == 190 or "token" in message or "authentication" in message:
        return "authentication_error"
    if status_code == 403 or code in {10, 200, 2000} or "permission" in message:
        return "permission_error"
    if code in {100, 131026} or "recipient" in message or "phone number" in message:
        return "invalid_recipient"
    if details:
        return "meta_api_error"
    return "unknown_provider_error"


def redact_meta_error_details(details: Mapping[str, Any] | None, secrets: Iterable[str]) -> dict[str, Any]:
    if not details:
        return {}
    safe: dict[str, Any] = {}
    configured_secrets = [secret for secret in secrets if secret]
    for key in ("http_status", "type", "code", "error_subcode", "message", "error_data_details", "fbtrace_id", "exception_type", "exception_message"):
        value = details.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            for secret in configured_secrets:
                value = value.replace(secret, "[REDACTED]")
        safe[key] = value
    return safe


def safe_exception_details(exc: BaseException, secrets: Iterable[str]) -> dict[str, str]:
    message = str(exc)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return {"exception_type": type(exc).__name__, "exception_message": message[:500]}