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
from app.schemas.admin_dashboard import (
    AdminDashboardSummaryResponse,
    DailyPerformanceResponse,
    DashboardPeriod,
    RecentOrderResponse,
    TopSellingItemResponse,
)

logger = logging.getLogger(__name__)

REVENUE_STATUSES = {"delivered", "completed"}
PLACED_STATUSES = {"pending", "confirmed", "preparing", "ready", "rider_assigned", "out_for_delivery", "delivered", "completed"}


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

    def _business_timezone(self):
        try:
            return ZoneInfo(settings.BUSINESS_TIMEZONE)
        except ZoneInfoNotFoundError:
            if settings.BUSINESS_TIMEZONE != "Asia/Karachi":
                raise RuntimeError(f"Business timezone data is unavailable for {settings.BUSINESS_TIMEZONE}.") from None
            return timezone(timedelta(hours=5), name="Asia/Karachi")

    def _today_bounds(self) -> tuple[datetime, datetime, date]:
        return business_day_bounds(settings.BUSINESS_TIMEZONE, now=self._clock() if self._clock else None)

    def _period_bounds(self, period: DashboardPeriod) -> tuple[datetime | None, datetime | None, date]:
        today_start, today_end, business_date = self._today_bounds()
        if period is DashboardPeriod.TODAY:
            return today_start, today_end, business_date
        if period is DashboardPeriod.SEVEN_DAYS:
            return today_start - timedelta(days=6), today_end, business_date
        if period is DashboardPeriod.THIRTY_DAYS:
            return today_start - timedelta(days=29), today_end, business_date
        return None, None, business_date

    @staticmethod
    def _range_conditions(start: datetime | None, end: datetime | None) -> list[object]:
        conditions: list[object] = []
        if start is not None:
            conditions.append(Order.created_at >= start)
        if end is not None:
            conditions.append(Order.created_at < end)
        return conditions

    @staticmethod
    def _next_month(month: date) -> date:
        return date(month.year + (month.month // 12), (month.month % 12) + 1, 1)

    def _count_customers(self) -> int:
        order_customers = select(func.lower(func.trim(Order.customer_phone)).label("customer_id")).where(
            Order.customer_phone.is_not(None), func.trim(Order.customer_phone) != ""
        )
        subscription_customers = select(func.lower(func.trim(CustomerSubscription.customer_phone)).label("customer_id")).where(
            CustomerSubscription.customer_phone.is_not(None), func.trim(CustomerSubscription.customer_phone) != ""
        )
        conversation_customers = select(func.lower(func.trim(ConversationStateRecord.customer_phone)).label("customer_id")).where(
            ConversationStateRecord.customer_phone.is_not(None), func.trim(ConversationStateRecord.customer_phone) != ""
        )
        customer_ids = union(order_customers, subscription_customers, conversation_customers).subquery()
        return int(self.db.scalar(select(func.count()).select_from(customer_ids)) or 0)

    def _count_orders(self, start: datetime | None, end: datetime | None, statuses: set[str] | None) -> int:
        conditions = self._range_conditions(start, end)
        if statuses is not None:
            conditions.append(Order.status.in_(statuses))
        return int(self.db.scalar(select(func.count(Order.id)).where(*conditions)) or 0)

    def _sum_revenue(self, start: datetime | None, end: datetime | None) -> Decimal:
        conditions = self._range_conditions(start, end)
        conditions.append(Order.status.in_(REVENUE_STATUSES))
        value = self.db.scalar(select(func.sum(Order.total_amount)).where(*conditions))
        return Decimal(str(value or Decimal("0.00")))

    def _status_counts(self) -> dict[str, int]:
        # Operational cards represent the current all-time order-state totals;
        # the selected period is applied to performance and revenue metrics.
        rows = self.db.execute(select(Order.status, func.count(Order.id)).group_by(Order.status)).all()
        return {str(status): int(count) for status, count in rows}

    def _top_selling_item(self, start: datetime | None, end: datetime | None) -> TopSellingItemResponse | None:
        conditions = self._range_conditions(start, end)
        conditions.append(Order.status.in_(PLACED_STATUSES))
        row = self.db.execute(
            select(
                Product.name,
                func.sum(OrderItem.quantity).label("quantity"),
                func.sum(OrderItem.subtotal).label("revenue"),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(*conditions)
            .group_by(Product.id, Product.name)
            .order_by(func.sum(OrderItem.quantity).desc(), Product.name.asc())
            .limit(1)
        ).first()
        if row is None:
            return None
        return TopSellingItemResponse(
            name=str(row[0]),
            quantity=int(row[1]),
            revenue=Decimal(str(row[2] or Decimal("0.00"))),
        )

    def _daily_performance(self, days: list[date]) -> list[DailyPerformanceResponse]:
        result: list[DailyPerformanceResponse] = []
        for day in days:
            day_start, day_end, _ = business_day_bounds(
                settings.BUSINESS_TIMEZONE,
                now=datetime.combine(day, datetime_time.min),
            )
            result.append(DailyPerformanceResponse(
                date=day.isoformat(),
                orders=self._count_orders(day_start, day_end, PLACED_STATUSES),
                revenue=self._sum_revenue(day_start, day_end),
            ))
        return result

    def _monthly_performance(self, business_date: date) -> list[DailyPerformanceResponse]:
        first_created = self.db.scalar(select(func.min(Order.created_at)))
        if first_created is None:
            first_month = business_date.replace(day=1)
        else:
            local_created = first_created if first_created.tzinfo else first_created.replace(tzinfo=timezone.utc)
            local_created = local_created.astimezone(self._business_timezone())
            first_month = date(local_created.year, local_created.month, 1)
        current_month = business_date.replace(day=1)
        result: list[DailyPerformanceResponse] = []
        month = first_month
        business_timezone = self._business_timezone()
        while month <= current_month:
            next_month = self._next_month(month)
            start_local = datetime.combine(month, datetime_time.min, tzinfo=business_timezone)
            end_local = datetime.combine(next_month, datetime_time.min, tzinfo=business_timezone)
            start_utc = start_local.astimezone(timezone.utc)
            end_utc = end_local.astimezone(timezone.utc)
            result.append(DailyPerformanceResponse(
                date=month.isoformat()[:7],
                orders=self._count_orders(start_utc, end_utc, PLACED_STATUSES),
                revenue=self._sum_revenue(start_utc, end_utc),
            ))
            month = next_month
        return result

    def _performance(self, period: DashboardPeriod) -> list[DailyPerformanceResponse]:
        _, _, business_date = self._today_bounds()
        if period is DashboardPeriod.TODAY:
            return self._daily_performance([business_date])
        if period is DashboardPeriod.SEVEN_DAYS:
            return self._daily_performance([business_date - timedelta(days=6 - offset) for offset in range(7)])
        if period is DashboardPeriod.THIRTY_DAYS:
            return self._daily_performance([business_date - timedelta(days=29 - offset) for offset in range(30)])
        return self._monthly_performance(business_date)

    def get_summary(self, period: DashboardPeriod = DashboardPeriod.TODAY) -> AdminDashboardSummaryResponse:
        started = time.perf_counter()
        today_start, today_end, business_date = self._today_bounds()
        period_start, period_end, _ = self._period_bounds(period)
        status_counts = self._status_counts()
        total_orders = self._count_orders(None, None, PLACED_STATUSES)
        total_revenue = self._sum_revenue(None, None)
        period_orders = self._count_orders(period_start, period_end, PLACED_STATUSES)
        period_revenue = self._sum_revenue(period_start, period_end)
        active_subscriptions = int(self.db.scalar(select(func.count(CustomerSubscription.id)).where(
            CustomerSubscription.status == "active",
            CustomerSubscription.start_date <= business_date,
            CustomerSubscription.end_date >= business_date,
        )) or 0)
        recent_orders = list(self.db.scalars(select(Order).order_by(Order.created_at.desc(), Order.id.desc()).limit(5)).all())
        summary = AdminDashboardSummaryResponse(
            period=period,
            total_orders=total_orders,
            total_revenue=total_revenue,
            period_orders=period_orders,
            period_revenue=period_revenue,
            today_orders=self._count_orders(today_start, today_end, None),
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
            today_revenue=self._sum_revenue(today_start, today_end),
            active_subscriptions=active_subscriptions,
            total_customers=self._count_customers(),
            top_selling_item=self._top_selling_item(period_start, period_end),
            performance=self._performance(period),
            recent_orders=[RecentOrderResponse.model_validate(order) for order in recent_orders],
        )
        logger.info("admin_dashboard_summary_generated", extra={
            "event": "admin_dashboard_summary_generated",
            "period": period.value,
            "period_orders": period_orders,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        })
        return summary
