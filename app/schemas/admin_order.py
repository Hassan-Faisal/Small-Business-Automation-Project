from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class AdminOrderItemResponse(BaseModel):
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class AdminOrderListItem(BaseModel):
    id: int
    order_number: str
    customer_phone: str
    status: str
    total_amount: Decimal
    created_at: datetime
    updated_at: datetime
    item_count: int
    delivery_provider: str | None = None


class AdminOrderListResponse(BaseModel):
    items: list[AdminOrderListItem]
    page: int
    page_size: int
    total: int
    pages: int


class AdminOrderDetailResponse(BaseModel):
    id: int
    order_number: str
    customer_phone: str
    status: str
    total_amount: Decimal
    delivery_address: str
    customer_notes: str | None = None
    internal_note: str | None = None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    estimated_delivery_minutes: int | None = None
    delivery_provider: str | None = None
    rider_note: str | None = None
    items: list[AdminOrderItemResponse]


class AdminOrderStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=50)

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        return value.strip().lower()


class AdminOrderDeliveryUpdate(BaseModel):
    estimated_delivery_minutes: int | None = Field(default=None, ge=1, le=1440)
    delivery_provider: str | None = Field(default=None, max_length=30)
    rider_note: str | None = Field(default=None, max_length=2000)
    internal_note: str | None = Field(default=None, max_length=2000)

    @field_validator("delivery_provider")
    @classmethod
    def normalize_provider(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in {"bykea", "yango", "uber", "other"}:
            raise ValueError("Unsupported delivery provider.")
        return normalized

    @model_validator(mode="after")
    def require_update(self) -> "AdminOrderDeliveryUpdate":
        if all(value is None for value in (self.estimated_delivery_minutes, self.delivery_provider, self.rider_note, self.internal_note)):
            raise ValueError("At least one delivery field is required.")
        return self


class AdminOrderFilters(BaseModel):
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "AdminOrderFilters":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from cannot be later than date_to.")
        return self

