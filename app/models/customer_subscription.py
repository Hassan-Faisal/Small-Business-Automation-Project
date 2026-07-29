from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.subscription_plan import SubscriptionPlan


class CustomerSubscription(Base):
    __tablename__ = "customer_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    subscription_plan_id: Mapped[int] = mapped_column(ForeignKey("subscription_plans.id"), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"), default="pending", nullable=False, index=True)
    delivery_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preferred_meal_choices: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    plan: Mapped["SubscriptionPlan"] = relationship()
