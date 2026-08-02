from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select, union
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.conversation_state import ConversationStateRecord
from app.models.customer_subscription import CustomerSubscription
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.admin_dashboard import AdminDashboardSummaryResponse, RecentOrderResponse, TopSellingItemResponse

logger = logging.getLogger(__name__)

SUPPORTED_DASHBOARD_STATUSES = {
    "draft",
    "pending",
    "confirmed",
    "preparing",
    "ready",
    "rider_assigned",
    "out_for_delivery",
    "delivered",
    "completed",
    "cancelled",
}
REVENUE_STATUSES = {"delivered", "completed"}
TOP_SELLING_STATUSES = {"confirmed", "delivered", "completed"}


def business_day_bounds(
    timezone_name: str,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime, date]:
    try:
        business_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name != "Asia/Karachi":
            raise RuntimeError(f"Business timezone data is unavailable for {timezone_name}.") from None
        business_timezone = timezone(timedelta(hours=5), name="Asia/Karachi")
    current = now or datetime.now(business_timezone)
    if current.tzinfo is None:
        current = current.replace(tzinfo=business_timezone)
    else:
        current = current.astimezone(business_timezone)
    start_local = datetime.combine(current.date(), datetime_time.min, tzinfo=business_timezone)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), current.date()


class AdminDashboardService:
    def __init__(self, db: Session, *, clock: Callable[[], datetime] | None = None) -> None:
        self.db = db
        self._clock = clock

    def _today_bounds(self) -> tuple[datetime, datetime, date]:
        return business_day_bounds(settings.BUSINESS_TIMEZONE, now=self._clock() if self._clock else None)

    def _count_customers(self) -> int:
        order_customers = select(func.lower(func.trim(Order.customer_phone)).label("customer_id")).where(
            Order.customer_phone.is_not(None),
            func.trim(Order.customer_phone) != "",
        )
        subscription_customers = select(func.lower(func.trim(CustomerSubscription.customer_phone)).label("customer_id")).where(
            CustomerSubscription.customer_phone.is_not(None),
            func.trim(CustomerSubscription.customer_phone) != "",
        )
        conversation_customers = select(func.lower(func.trim(ConversationStateRecord.customer_phone)).label("customer_id")).where(
            ConversationStateRecord.customer_phone.is_not(None),
            func.trim(ConversationStateRecord.customer_phone) != "",
        )
        customer_ids = union(order_customers, subscription_customers, conversation_customers).subquery()
        return int(self.db.scalar(select(func.count()).select_from(customer_ids)) or 0)

    def get_summary(self) -> AdminDashboardSummaryResponse:
        started = time.perf_counter()
        start_utc, end_utc, business_date = self._today_bounds()

        status_rows = self.db.execute(
            select(Order.status, func.count(Order.id))
            .where(Order.created_at >= start_utc, Order.created_at < end_utc)
            .group_by(Order.status)
        ).all()
        status_counts = {str(status): int(count) for status, count in status_rows}
        today_orders = sum(status_counts.values())

        revenue_value = self.db.scalar(
            select(func.sum(Order.total_amount)).where(
                Order.created_at >= start_utc,
                Order.created_at < end_utc,
                Order.status.in_(REVENUE_STATUSES),
            )
        )
        today_revenue = Decimal(str(revenue_value or Decimal("0.00")))

        active_subscriptions = int(
            self.db.scalar(
                select(func.count(CustomerSubscription.id)).where(
                    CustomerSubscription.status == "active",
                    CustomerSubscription.start_date <= business_date,
                    CustomerSubscription.end_date >= business_date,
                )
            )
            or 0
        )
        total_customers = self._count_customers()

        top_selling_row = self.db.execute(
            select(Product.name, func.sum(OrderItem.quantity).label("quantity"))
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.created_at >= start_utc,
                Order.created_at < end_utc,
                Order.status.in_(TOP_SELLING_STATUSES),
            )
            .group_by(Product.id, Product.name)
            .order_by(func.sum(OrderItem.quantity).desc(), Product.name.asc())
            .limit(1)
        ).first()
        top_selling_item = TopSellingItemResponse(name=str(top_selling_row[0]), quantity=int(top_selling_row[1])) if top_selling_row else None

        recent_orders = list(
            self.db.scalars(
                select(Order).order_by(Order.created_at.desc(), Order.id.desc()).limit(5)
            ).all()
        )

        summary = AdminDashboardSummaryResponse(
            today_orders=today_orders,
            pending_orders=status_counts.get("pending", 0) + status_counts.get("draft", 0),
            draft_orders=status_counts.get("draft", 0),
            confirmed_orders=status_counts.get("confirmed", 0),
            preparing_orders=status_counts.get("preparing", 0),
            ready_orders=status_counts.get("ready", 0),
            rider_assigned_orders=status_counts.get("rider_assigned", 0),
            out_for_delivery_orders=status_counts.get("out_for_delivery", 0),
            delivered_orders=status_counts.get("delivered", 0),
            completed_orders=status_counts.get("completed", 0),
            cancelled_orders=status_counts.get("cancelled", 0),
            today_revenue=today_revenue,
            active_subscriptions=active_subscriptions,
            total_customers=total_customers,
            top_selling_item=top_selling_item,
            recent_orders=[RecentOrderResponse.model_validate(order) for order in recent_orders],
        )
        logger.info(
            "admin_dashboard_summary_generated",
            extra={
                "event": "admin_dashboard_summary_generated",
                "today_orders": today_orders,
                "active_subscriptions": active_subscriptions,
                "total_customers": total_customers,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return summary