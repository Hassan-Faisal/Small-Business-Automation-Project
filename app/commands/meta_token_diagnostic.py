from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.config import settings


_LABELS = (
    "Token type",
    "App ID",
    "Application name",
    "User ID",
    "Scopes",
    "is_valid",
    "expires_at",
    "granular_scopes",
    "phone_number_id",
    "display_phone_number",
    "verified_name",
)


def _value(payload: Mapping[str, Any] | None, key: str, default: Any = "Unavailable") -> Any:
    if not isinstance(payload, Mapping):
        return default
    value = payload.get(key)
    return default if value is None else value


def _json_response(response: httpx.Response | None) -> Mapping[str, Any] | None:
    if response is None or not response.is_success:
        return None
    try:
        payload = response.json()
    except (ValueError, TypeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _display(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=True)
    return str(value)


def main() -> int:
    token = settings.WHATSAPP_ACCESS_TOKEN.strip()
    phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID.strip()
    api_version = settings.WHATSAPP_API_VERSION.strip() or "v21.0"
    debug_data: Mapping[str, Any] | None = None
    me_data: Mapping[str, Any] | None = None
    phone_data: Mapping[str, Any] | None = None
    success = bool(token and phone_number_id)

    if token and phone_number_id:
        headers = {"Authorization": f"Bearer {token}"}
        base_url = f"https://graph.facebook.com/{api_version}"
        try:
            with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                debug_response = client.get(f"{base_url}/debug_token", params={"input_token": token}, headers=headers)
                me_response = client.get(f"{base_url}/me", params={"fields": "id,name"}, headers=headers)
                phone_response = client.get(f"{base_url}/{phone_number_id}", params={"fields": "id,display_phone_number,verified_name"}, headers=headers)
            debug_payload = _json_response(debug_response)
            me_data = _json_response(me_response)
            phone_data = _json_response(phone_response)
            debug_data_value = debug_payload.get("data") if isinstance(debug_payload, Mapping) else None
            debug_data = debug_data_value if isinstance(debug_data_value, Mapping) else None
            success = success and debug_data is not None and me_data is not None and phone_data is not None
        except httpx.HTTPError:
            success = False
    for label in _LABELS:
        if label == "Token type":
            value = _value(debug_data, "type")
        elif label == "App ID":
            value = _value(debug_data, "app_id")
        elif label == "Application name":
            value = _value(debug_data, "application")
        elif label == "User ID":
            value = _value(debug_data, "user_id", _value(me_data, "id"))
        elif label == "Scopes":
            value = _value(debug_data, "scopes", [])
        elif label == "is_valid":
            value = _value(debug_data, "is_valid")
        elif label == "expires_at":
            value = _value(debug_data, "expires_at")
        elif label == "granular_scopes":
            value = _value(debug_data, "granular_scopes", [])
        elif label == "phone_number_id":
            value = _value(phone_data, "id", phone_number_id if phone_number_id else "Unavailable")
        elif label == "display_phone_number":
            value = _value(phone_data, "display_phone_number")
        else:
            value = _value(phone_data, "verified_name")
        print(f"{label}: {_display(value)}")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
