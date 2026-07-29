from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MealOfferingBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    meal_type: str = Field(min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=10_000)
    price: Decimal = Field(ge=Decimal("0.00"))
    day_of_week: str = Field(min_length=1, max_length=20)
    availability: bool = True
    is_active: bool = True


class MealOfferingResponse(MealOfferingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
