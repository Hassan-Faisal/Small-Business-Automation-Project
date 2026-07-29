from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


class ConversationStateRecord(Base):
    __tablename__ = "conversation_state_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    customer_phone: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    cart: Mapped[list[dict] | None] = mapped_column(JSON, nullable=False, default=list)
    messages: Mapped[list[dict] | None] = mapped_column(JSON, nullable=False, default=list)
    processed_message_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=False, default=list)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    order_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    last_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
