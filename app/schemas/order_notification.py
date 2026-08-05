from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

NotificationStatus = Literal["sent", "failed", "skipped"]


class NotificationResult(BaseModel):
    status: NotificationStatus
    message_sid: str | None = None
    reason: str | None = None

