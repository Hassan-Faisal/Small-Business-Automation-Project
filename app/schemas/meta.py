from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MetaEmbeddedSignupConfigResponse(BaseModel):
    app_id: str
    config_id: str


class MetaEmbeddedSignupCompletionRequest(BaseModel):
    event: Literal["FINISH"]
    code: str = Field(min_length=1, max_length=4096)
    waba_id: str = Field(min_length=1, max_length=128)
    phone_number_id: str = Field(min_length=1, max_length=128)


class MetaEmbeddedSignupCompletionResponse(BaseModel):
    status: Literal["completed"]
    waba_id: str
    phone_number_id: str
    access_token_exchanged: bool
