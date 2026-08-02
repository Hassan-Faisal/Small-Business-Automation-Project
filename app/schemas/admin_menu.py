from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner"}
CANONICAL_DAYS = {day.lower(): day for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")}


def normalize_menu_name(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("Menu item name is required.")
    return normalized


def normalize_meal_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in VALID_MEAL_TYPES:
        raise ValueError("Meal type must be breakfast, lunch, or dinner.")
    return normalized


def normalize_day_of_week(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in CANONICAL_DAYS:
        raise ValueError("Day of week must be Monday through Sunday.")
    return CANONICAL_DAYS[normalized]


def normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class AdminMenuItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=10_000)
    price: Decimal = Field(gt=Decimal("0.00"), max_digits=10, decimal_places=2)
    meal_type: str = Field(min_length=1, max_length=20)
    day_of_week: str = Field(min_length=1, max_length=20)
    availability: bool = True
    is_active: bool = True

    _normalize_name = field_validator("name")(normalize_menu_name)
    _normalize_meal_type = field_validator("meal_type")(normalize_meal_type)
    _normalize_day = field_validator("day_of_week")(normalize_day_of_week)
    _normalize_description = field_validator("description")(normalize_description)


class AdminMenuItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=10_000)
    price: Decimal | None = Field(default=None, gt=Decimal("0.00"), max_digits=10, decimal_places=2)
    meal_type: str | None = Field(default=None, min_length=1, max_length=20)
    day_of_week: str | None = Field(default=None, min_length=1, max_length=20)
    availability: bool | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Menu item name cannot be null.")
        return normalize_menu_name(value)

    @field_validator("meal_type")
    @classmethod
    def validate_meal_type(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Meal type cannot be null.")
        return normalize_meal_type(value)

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Day of week cannot be null.")
        return normalize_day_of_week(value)

    _normalize_description = field_validator("description")(normalize_description)

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: Decimal | None) -> Decimal:
        if value is None:
            raise ValueError("Price cannot be null.")
        return value

    @field_validator("availability", "is_active")
    @classmethod
    def validate_flags(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("Availability and active flags cannot be null.")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "AdminMenuItemUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one menu item field must be provided.")
        return self


class AdminMenuAvailabilityUpdate(BaseModel):
    availability: bool


class AdminMenuItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price: Decimal
    meal_type: str
    day_of_week: str
    availability: bool
    is_active: bool


class AdminMenuItemListResponse(BaseModel):
    items: list[AdminMenuItemResponse]
    total: int
    page: int
    page_size: int


class AdminMenuItemDeactivationResponse(BaseModel):
    id: int
    message: str
    availability: bool
    is_active: bool
