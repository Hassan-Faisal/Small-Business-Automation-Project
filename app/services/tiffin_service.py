from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer_subscription import CustomerSubscription
from app.models.meal_offering import MealOffering
from app.models.meal_skip import MealSkip
from app.models.subscription_plan import SubscriptionPlan

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DELIVERY_WINDOWS = {
    "breakfast": time(8, 0),
    "lunch": time(13, 0),
    "dinner": time(21, 0),
}
SUPPORTED_PAYMENT_METHODS = {"cash_on_delivery", "online_transfer", "bank_transfer"}
SUPPORTED_SUBSCRIPTION_STATUSES = {"pending", "active", "paused", "completed", "cancelled"}
BULK_ORDER_THRESHOLD = 10
ALLOWED_SUBSCRIPTION_TRANSITIONS = {
    "pending": {"active", "cancelled"},
    "active": {"paused", "cancelled"},
    "paused": {"active", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


@dataclass(slots=True)
class BulkOrderValidationResult:
    is_valid: bool
    reason: str | None = None


@dataclass(slots=True)
class MealSkipValidationResult:
    is_valid: bool
    reason: str | None = None


class TiffinCatalogService:
    def __init__(self, db: Session):
        self.db = db

    def list_meal_offerings(
        self,
        *,
        day_of_week: str | None = None,
        meal_type: str | None = None,
        active_only: bool = True,
    ) -> list[MealOffering]:
        stmt = select(MealOffering)
        if day_of_week is not None:
            stmt = stmt.where(func.lower(MealOffering.day_of_week) == day_of_week.strip().lower())
        if meal_type is not None:
            stmt = stmt.where(func.lower(MealOffering.meal_type) == meal_type.strip().lower())
        if active_only:
            stmt = stmt.where(MealOffering.is_active.is_(True), MealOffering.availability.is_(True))
        return list(self.db.scalars(stmt.order_by(MealOffering.day_of_week, MealOffering.meal_type, MealOffering.name)).all())

    def list_weekly_menu(self) -> dict[str, dict[str, list[MealOffering]]]:
        weekly: dict[str, dict[str, list[MealOffering]]] = {day: {"breakfast": [], "lunch": [], "dinner": []} for day in WEEKDAYS}
        for offering in self.list_meal_offerings(active_only=True):
            weekly.setdefault(offering.day_of_week, {"breakfast": [], "lunch": [], "dinner": []})[offering.meal_type].append(offering)
        return weekly

    def list_daily_menu(self, day_of_week: str) -> dict[str, list[MealOffering]]:
        weekly = self.list_weekly_menu()
        return weekly.get(day_of_week.strip().title(), {"breakfast": [], "lunch": [], "dinner": []})

    def list_meals_for_day_and_type(self, day_of_week: str, meal_type: str) -> list[MealOffering]:
        return self.list_meal_offerings(day_of_week=day_of_week, meal_type=meal_type)

    def format_daily_menu(self, day_of_week: str) -> str:
        menu = self.list_daily_menu(day_of_week)
        lines: list[str] = [f"{day_of_week.strip().title()} menu:"]
        for meal_type in ("breakfast", "lunch", "dinner"):
            items = menu.get(meal_type, [])
            if not items:
                continue
            lines.append(f"{meal_type.title()}:")
            for item in items:
                lines.append(f"- {item.name} - Rs. {item.price}")
        return "\n".join(lines)


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    def list_subscription_plans(self) -> list[SubscriptionPlan]:
        stmt = select(SubscriptionPlan).where(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.number_of_days, SubscriptionPlan.name)
        return list(self.db.scalars(stmt).all())

    def retrieve_subscription_plan(self, plan_id: int) -> SubscriptionPlan | None:
        return self.db.get(SubscriptionPlan, plan_id)

    def get_pending_subscription(self, customer_phone: str) -> CustomerSubscription | None:
        stmt = select(CustomerSubscription).where(
            func.lower(func.trim(CustomerSubscription.customer_phone)) == customer_phone.strip().lower(),
            CustomerSubscription.status == "pending",
        ).order_by(CustomerSubscription.created_at.desc())
        return self.db.scalars(stmt).first()

    def update_subscription_status(self, subscription: CustomerSubscription, new_status: str) -> CustomerSubscription:
        if new_status not in SUPPORTED_SUBSCRIPTION_STATUSES:
            raise ValueError("Unsupported subscription status.")
        allowed = ALLOWED_SUBSCRIPTION_TRANSITIONS.get(subscription.status, set())
        if new_status != subscription.status and new_status not in allowed:
            raise ValueError(f"Cannot transition subscription from {subscription.status} to {new_status}.")
        subscription.status = new_status
        self.db.flush()
        self.db.commit()
        return self.db.get(CustomerSubscription, subscription.id) or subscription

    def cancel_customer_subscription(self, customer_phone: str) -> CustomerSubscription | None:
        subscription = self.get_pending_subscription(customer_phone)
        if subscription is None:
            subscription = self.get_active_subscription(customer_phone)
        if subscription is None:
            subscription = self.db.scalars(
                select(CustomerSubscription).where(
                    func.lower(func.trim(CustomerSubscription.customer_phone)) == customer_phone.strip().lower(),
                    CustomerSubscription.status == "paused",
                ).order_by(CustomerSubscription.created_at.desc())
            ).first()
        if subscription is None:
            return None
        return self.update_subscription_status(subscription, "cancelled")

    def create_customer_subscription(
        self,
        *,
        customer_phone: str,
        subscription_plan_id: int,
        start_date: date,
        end_date: date,
        delivery_address: str | None,
        preferred_meal_choices: list[str],
        payment_method: str | None,
        status: str = "pending",
    ) -> CustomerSubscription:
        if status not in SUPPORTED_SUBSCRIPTION_STATUSES:
            raise ValueError("Unsupported subscription status.")
        subscription = CustomerSubscription(
            customer_phone=customer_phone.strip(),
            subscription_plan_id=subscription_plan_id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            delivery_address=delivery_address,
            preferred_meal_choices=preferred_meal_choices,
            payment_method=payment_method,
        )
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def get_active_subscription(self, customer_phone: str, on_date: date | None = None) -> CustomerSubscription | None:
        current_date = on_date or date.today()
        stmt = select(CustomerSubscription).where(
            func.lower(func.trim(CustomerSubscription.customer_phone)) == customer_phone.strip().lower(),
            CustomerSubscription.status == "active",
            CustomerSubscription.start_date <= current_date,
            CustomerSubscription.end_date >= current_date,
        ).order_by(CustomerSubscription.start_date.desc())
        return self.db.scalars(stmt).first()

    def get_customer_subscription_context(self, customer_phone: str, on_date: date | None = None) -> dict[str, Any]:
        current_date = on_date or date.today()
        subscription = self.get_active_subscription(customer_phone, current_date)
        if subscription is None:
            return {"has_active_subscription": False, "subscription": None, "included_meals_today": [], "status": None, "start_date": None, "end_date": None}
        plan = subscription.plan or self.retrieve_subscription_plan(subscription.subscription_plan_id)
        included_meals_today = self.get_included_meals_for_subscription(subscription, current_date)
        return {
            "has_active_subscription": True,
            "subscription": subscription,
            "plan": plan,
            "included_meals_today": included_meals_today,
            "status": subscription.status,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
        }

    def get_included_meals_for_subscription(self, subscription: CustomerSubscription, on_date: date | None = None) -> list[str]:
        _ = on_date or date.today()
        plan = subscription.plan or self.retrieve_subscription_plan(subscription.subscription_plan_id)
        if plan is None:
            return []
        return [str(meal_type) for meal_type in plan.included_meal_types if str(meal_type) in {"breakfast", "lunch", "dinner"}]


    def pause_customer_subscription(self, customer_phone: str) -> CustomerSubscription | None:
        subscription = self.get_active_subscription(customer_phone)
        if subscription is None:
            return None
        return self.update_subscription_status(subscription, "paused")

    def resume_customer_subscription(self, customer_phone: str, on_date: date | None = None) -> CustomerSubscription | None:
        subscription = self.db.scalars(
            select(CustomerSubscription).where(
                func.lower(func.trim(CustomerSubscription.customer_phone)) == customer_phone.strip().lower(),
                CustomerSubscription.status == "paused",
            ).order_by(CustomerSubscription.start_date.desc())
        ).first()
        if subscription is None:
            return None
        current_date = on_date or date.today()
        target_status = "active" if subscription.start_date <= current_date <= subscription.end_date else "pending"
        return self.update_subscription_status(subscription, target_status)

class TiffinPolicyService:
    def __init__(self, db: Session):
        self.db = db

    def validate_meal_skip(
        self,
        *,
        subscription: CustomerSubscription,
        meal_date: date,
        meal_type: str,
        requested_at: datetime | None = None,
        reason: str | None = None,
    ) -> MealSkipValidationResult:
        if meal_type not in DELIVERY_WINDOWS:
            return MealSkipValidationResult(is_valid=False, reason="Unsupported meal type.")
        request_time = requested_at or datetime.now(timezone.utc)
        if request_time.tzinfo is None:
            request_time = request_time.replace(tzinfo=timezone.utc)
        delivery_start = datetime.combine(meal_date, DELIVERY_WINDOWS[meal_type], tzinfo=timezone.utc)
        deadline = delivery_start - timedelta(hours=12)
        if request_time > deadline:
            return MealSkipValidationResult(is_valid=False, reason="Meal skips must be requested at least 12 hours before delivery.")
        skip = MealSkip(subscription_id=subscription.id, meal_date=meal_date, meal_type=meal_type, reason=reason, requested_at=request_time, status="pending")
        self.db.add(skip)
        self.db.commit()
        self.db.refresh(skip)
        return MealSkipValidationResult(is_valid=True)

    def validate_bulk_order(self, *, requested_delivery_at: datetime, number_of_boxes: int, threshold: int = BULK_ORDER_THRESHOLD) -> BulkOrderValidationResult:
        if number_of_boxes < threshold:
            return BulkOrderValidationResult(is_valid=True)
        now = datetime.now(timezone.utc)
        if requested_delivery_at.tzinfo is None:
            requested_delivery_at = requested_delivery_at.replace(tzinfo=timezone.utc)
        if requested_delivery_at - now < timedelta(hours=24):
            return BulkOrderValidationResult(is_valid=False, reason="Bulk orders must be placed at least 24 hours in advance.")
        return BulkOrderValidationResult(is_valid=True)
