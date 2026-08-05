from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.admin_user import AdminUser
from app.models.order import Order
from app.models.order_item import OrderItem

from app.schemas.order_notification import NotificationResult
from app.services.order_notification_service import OrderNotificationService

from app.schemas.admin_order import (
    AdminOrderDeliveryUpdate,
    AdminOrderDetailResponse,
    AdminOrderFilters,
    AdminOrderItemResponse,
    AdminOrderListItem,
    AdminOrderListResponse,
)

logger = logging.getLogger(__name__)

STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"confirmed", "cancelled"},
    "confirmed": {"preparing", "cancelled"},
    "preparing": {"ready", "cancelled"},
    "ready": {"rider_assigned"},
    "rider_assigned": {"out_for_delivery"},
    "out_for_delivery": {"completed"},
    "delivered": {"completed"},
}
TERMINAL_STATUSES = {"completed", "cancelled"}
SUPPORTED_STATUSES = set(STATUS_TRANSITIONS) | set().union(*STATUS_TRANSITIONS.values()) | TERMINAL_STATUSES


class AdminOrderNotFoundError(ValueError):
    pass


class AdminOrderInvalidStatusError(ValueError):
    pass


class AdminOrderInvalidTransitionError(ValueError):
    pass


class AdminOrderTransactionError(RuntimeError):
    pass


class AdminOrderService:
    def __init__(self, db: Session, notification_service: OrderNotificationService | None = None) -> None:
        self.db = db
        self.notification_service = notification_service or OrderNotificationService()

    @staticmethod
    def _bounds(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
        filters = AdminOrderFilters(date_from=date_from, date_to=date_to)
        start = datetime.combine(filters.date_from, time.min) if filters.date_from else None
        end = datetime.combine(filters.date_to, time.max) if filters.date_to else None
        return start, end

    def list_orders(
        self, *, status: str | None, date_from: date | None, date_to: date | None,
        customer_phone: str | None, order_number: str | None, search: str | None,
        page: int, page_size: int,
    ) -> AdminOrderListResponse:
        start, end = self._bounds(date_from, date_to)
        item_counts = select(func.count(OrderItem.id)).where(OrderItem.order_id == Order.id).scalar_subquery()
        conditions = []
        if status:
            conditions.append(Order.status == status.strip().lower())
        if start:
            conditions.append(Order.created_at >= start)
        if end:
            conditions.append(Order.created_at <= end)
        if customer_phone:
            conditions.append(Order.customer_phone.ilike(f"%{customer_phone.strip()}%"))
        if order_number:
            conditions.append(Order.order_number.ilike(f"%{order_number.strip()}%"))
        if search:
            term = f"%{search.strip()}%"
            conditions.append(or_(Order.order_number.ilike(term), Order.customer_phone.ilike(term)))
        total = int(self.db.scalar(select(func.count(Order.id)).where(*conditions)) or 0)
        rows = self.db.execute(
            select(Order, item_counts.label("item_count"))
            .where(*conditions)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = [
            AdminOrderListItem.model_validate({
                "id": order.id, "order_number": order.order_number,
                "customer_phone": order.customer_phone, "status": order.status,
                "total_amount": order.total_amount, "created_at": order.created_at,
                "updated_at": order.updated_at, "item_count": int(item_count),
                "delivery_provider": order.delivery_provider,
            })
            for order, item_count in rows
        ]
        logger.info("admin_order_list_generated", extra={
            "event": "admin_order_list_generated", "page": page,
            "page_size": page_size, "result_count": len(items),
        })
        return AdminOrderListResponse(
            items=items, page=page, page_size=page_size, total=total,
            pages=(total + page_size - 1) // page_size,
        )

    def _get_order(self, order_id: int, *, for_update: bool = False) -> Order:
        statement = select(Order).where(Order.id == order_id).options(
            selectinload(Order.items).selectinload(OrderItem.product)
        )
        if for_update:
            statement = statement.with_for_update()
        order = self.db.scalar(statement)
        if order is None:
            raise AdminOrderNotFoundError("Order not found.")
        return order

    def get_detail(self, order_id: int) -> AdminOrderDetailResponse:
        order = self._get_order(order_id)
        logger.info("admin_order_detail_accessed", extra={
            "event": "admin_order_detail_accessed", "order_id": order_id,
        })
        return AdminOrderDetailResponse(
            id=order.id, order_number=order.order_number,
            customer_phone=order.customer_phone, status=order.status,
            total_amount=order.total_amount, delivery_address=order.delivery_address,
            customer_notes=order.special_instructions, internal_note=order.internal_note,
            created_at=order.created_at, updated_at=order.updated_at,
            confirmed_at=order.confirmed_at, completed_at=order.completed_at,
            cancelled_at=order.cancelled_at,
            estimated_delivery_minutes=order.estimated_delivery_minutes,
            delivery_provider=order.delivery_provider, rider_note=order.rider_note,
            items=[AdminOrderItemResponse(
                product_name=item.product.name, quantity=item.quantity,
                unit_price=item.unit_price, subtotal=item.subtotal,
            ) for item in order.items],
        )

    def _notify_status_safely(self, order: Order) -> NotificationResult:
        try:
            return self.notification_service.notify_status(order)
        except Exception:
            logger.exception("order_status_notification_failed", extra={"event": "order_status_notification_failed", "order_id": order.id, "order_number": order.order_number, "status": order.status})
            return NotificationResult(status="failed", reason="notification_service_error")

    def _notify_delivery_safely(self, order: Order) -> NotificationResult:
        try:
            return self.notification_service.notify_delivery_update(order)
        except Exception:
            logger.exception("order_delivery_notification_failed", extra={"event": "order_delivery_notification_failed", "order_id": order.id, "order_number": order.order_number, "status": order.status})
            return NotificationResult(status="failed", reason="notification_service_error")

    def update_status(self, order_id: int, new_status: str, admin: AdminUser) -> AdminOrderDetailResponse:
        order = self._get_order(order_id, for_update=True)
        old_status = order.status
        if old_status in TERMINAL_STATUSES or new_status not in STATUS_TRANSITIONS.get(old_status, set()):
            raise AdminOrderInvalidTransitionError(f"Cannot transition order from {old_status} to {new_status}.")
        now = datetime.now(timezone.utc)
        order.status = new_status
        order.updated_at = now
        if new_status == "confirmed":
            order.confirmed_at = now
        elif new_status == "completed":
            order.completed_at = now
        elif new_status == "cancelled":
            order.cancelled_at = now
        try:
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise AdminOrderTransactionError("Unable to update order status.") from exc
        logger.info("admin_order_status_changed", extra={
            "event": "admin_order_status_changed", "order_id": order_id,
            "old_status": old_status, "new_status": new_status, "admin_id": admin.id,
        })
        self._notify_status_safely(order)
        return self.get_detail(order_id)

    def update_delivery(self, order_id: int, payload: AdminOrderDeliveryUpdate, admin: AdminUser) -> AdminOrderDetailResponse:
        order = self._get_order(order_id, for_update=True)
        old_eta = order.estimated_delivery_minutes
        old_provider = order.delivery_provider
        for field in ("estimated_delivery_minutes", "delivery_provider", "rider_note", "internal_note"):
            value = getattr(payload, field)
            if value is not None:
                setattr(order, field, value)
        order.updated_at = datetime.now(timezone.utc)
        try:
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise AdminOrderTransactionError("Unable to update delivery details.") from exc
        logger.info("admin_order_delivery_updated", extra={
            "event": "admin_order_delivery_updated", "order_id": order_id, "admin_id": admin.id,
        })
        if order.status in {"rider_assigned", "out_for_delivery"} and (old_eta != order.estimated_delivery_minutes or old_provider != order.delivery_provider):
            self._notify_delivery_safely(order)
        return self.get_detail(order_id)



