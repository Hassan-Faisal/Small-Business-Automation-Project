from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.order_item import OrderItem


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    delivery_address: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", server_default=text("'draft'"), nullable=False, index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), server_default=text("0.00"), nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_bulk_order: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    requested_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    number_of_boxes: Mapped[int | None] = mapped_column(nullable=True)
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_delivery_minutes: Mapped[int | None] = mapped_column(nullable=True)
    delivery_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rider_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan", passive_deletes=True)

