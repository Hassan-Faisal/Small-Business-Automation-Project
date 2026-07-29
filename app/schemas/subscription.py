from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SubscriptionPlanBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    duration_type: str = Field(min_length=1, max_length=20)
    number_of_days: int = Field(ge=1)
    included_meal_types: list[str]
    price: Decimal = Field(ge=Decimal("0.00"))
    description: str | None = Field(default=None, max_length=10_000)
    is_active: bool = True


class SubscriptionPlanResponse(SubscriptionPlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class CustomerSubscriptionBase(BaseModel):
    customer_phone: str = Field(min_length=1, max_length=30)
    subscription_plan_id: int = Field(ge=1)
    start_date: date
    end_date: date
    status: str = Field(min_length=1, max_length=20)
    delivery_address: str | None = Field(default=None, max_length=500)
    preferred_meal_choices: list[str] = Field(default_factory=list)
    payment_method: str | None = Field(default=None, max_length=30)


class CustomerSubscriptionResponse(CustomerSubscriptionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class MealSkipBase(BaseModel):
    subscription_id: int = Field(ge=1)
    meal_date: date
    meal_type: str = Field(min_length=1, max_length=20)
    reason: str | None = Field(default=None, max_length=10_000)
    status: str = Field(min_length=1, max_length=20)


class MealSkipResponse(MealSkipBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requested_at: datetime
