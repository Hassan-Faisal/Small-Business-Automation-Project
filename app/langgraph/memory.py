from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation_state import ConversationStateRecord


class ConversationMemory:
    """Persistent conversation store for LangGraph development and webhook idempotency."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _load_record(self, conversation_id: str) -> ConversationStateRecord | None:
        stmt = select(ConversationStateRecord).where(ConversationStateRecord.conversation_id == conversation_id)
        return self.db.scalars(stmt).first()

    def get(self, conversation_id: str) -> dict[str, object]:
        record = self._load_record(conversation_id)
        if record is None:
            return {
                "cart": [],
                "messages": [],
                "processed_message_ids": [],
                "address": None,
                "order_number": None,
                "order_status": None,
                "customer_phone": None,
                "last_response": None,
            }

        return {
            "cart": list(record.cart or []),
            "messages": list(record.messages or []),
            "processed_message_ids": list(record.processed_message_ids or []),
            "address": record.address,
            "order_number": record.order_number,
            "order_status": record.order_status,
            "customer_phone": record.customer_phone,
            "last_response": record.last_response,
        }

    def save(self, conversation_id: str, **values: object) -> None:
        record = self._load_record(conversation_id)
        if record is None:
            record = ConversationStateRecord(conversation_id=conversation_id, cart=[], messages=[], processed_message_ids=[])
            self.db.add(record)

        if "cart" in values:
            record.cart = list(values["cart"] or [])
        if "messages" in values:
            record.messages = list(values["messages"] or [])
        if "processed_message_ids" in values:
            record.processed_message_ids = list(values["processed_message_ids"] or [])
        if "address" in values:
            record.address = values["address"] if values["address"] is None or isinstance(values["address"], str) else str(values["address"])
        if "order_number" in values:
            record.order_number = values["order_number"] if values["order_number"] is None or isinstance(values["order_number"], str) else str(values["order_number"])
        if "order_status" in values:
            record.order_status = values["order_status"] if values["order_status"] is None or isinstance(values["order_status"], str) else str(values["order_status"])
        if "customer_phone" in values:
            record.customer_phone = values["customer_phone"] if values["customer_phone"] is None or isinstance(values["customer_phone"], str) else str(values["customer_phone"])
        if "last_response" in values:
            record.last_response = values["last_response"] if values["last_response"] is None or isinstance(values["last_response"], str) else str(values["last_response"])

        self.db.commit()
        self.db.refresh(record)

    def clear_expired_cart(self, conversation_id: str, max_age: timedelta, now: datetime | None = None) -> bool:
        """Clear only an inactive unplaced cart using the existing state timestamp."""
        record = self._load_record(conversation_id)
        if record is None or not list(record.cart or []):
            return False
        updated_at = record.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        current_time = now or datetime.now(timezone.utc)
        if current_time - updated_at <= max_age:
            return False
        record.cart = []
        self.db.commit()
        self.db.refresh(record)
        return True

    def has_processed_message(self, conversation_id: str, message_id: str) -> bool:
        record = self._load_record(conversation_id)
        return bool(record and message_id in list(record.processed_message_ids or []))

    def mark_processed_message(self, conversation_id: str, message_id: str) -> None:
        record = self._load_record(conversation_id)
        if record is None:
            record = ConversationStateRecord(conversation_id=conversation_id, cart=[], messages=[], processed_message_ids=[message_id])
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            return

        processed = list(record.processed_message_ids or [])
        if message_id not in processed:
            processed.append(message_id)
            record.processed_message_ids = processed
            self.db.commit()
            self.db.refresh(record)

    def clear(self, conversation_id: str) -> None:
        record = self._load_record(conversation_id)
        if record is not None:
            self.db.delete(record)
            self.db.commit()
