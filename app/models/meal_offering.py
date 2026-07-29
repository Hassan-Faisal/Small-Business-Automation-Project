from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MealOffering(Base):
    __tablename__ = "meal_offerings"
    __table_args__ = (
        UniqueConstraint("day_of_week", "meal_type", "name", name="uq_meal_offerings_day_type_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    day_of_week: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    availability: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True, nullable=False)
