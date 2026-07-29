from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, JSON, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    duration_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    number_of_days: Mapped[int] = mapped_column(nullable=False)
    included_meal_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True, nullable=False)
