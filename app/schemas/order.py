from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "OrderItemCreate",
    "OrderItemResponse",
    "OrderCreate",
    "OrderResponse",
    "OrderStatusUpdate",
]


class OrderItemBase(BaseModel):
    product_id: int
    quantity: int

    @field_validator("product_id", mode="before")
    @classmethod
    def validate_product_id(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Product ID must be greater than zero.")
        return value

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Quantity must be greater than zero.")
        return value


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class OrderBase(BaseModel):
    order_number: str | None = Field(default=None, max_length=50)
    customer_phone: str = Field(min_length=1, max_length=30)
    delivery_address: str = Field(min_length=1, max_length=500)
    payment_method: str | None = Field(default=None, max_length=30)
    is_bulk_order: bool = False
    requested_delivery_at: datetime | None = None
    number_of_boxes: int | None = Field(default=None, ge=1)
    special_instructions: str | None = Field(default=None, max_length=2000)


class OrderCreate(OrderBase):
    items: list[OrderItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_items(self) -> "OrderCreate":
        if not self.items:
            raise ValueError("Order must contain at least one item.")
        return self


class OrderStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=50)


class OrderResponse(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    total_amount: Decimal
    items: list[OrderItemResponse]
