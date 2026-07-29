from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.order import Order
from app.schemas.order import OrderCreate
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.tiffin_service import (
    BULK_ORDER_THRESHOLD,
    DELIVERY_WINDOWS,
    SUPPORTED_PAYMENT_METHODS,
    SubscriptionService,
    TiffinCatalogService,
    TiffinPolicyService,
)


def test_weekly_menu_retrieval(seeded_tiffin_catalog: TiffinCatalogService) -> None:
    weekly_menu = seeded_tiffin_catalog.list_weekly_menu()

    assert set(weekly_menu.keys()) == {
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
    }
    assert len(weekly_menu['Monday']['breakfast']) == 3
    assert len(weekly_menu['Friday']['lunch']) == 3
    assert len(weekly_menu['Sunday']['dinner']) == 3


def test_daily_menu_and_meal_type_filtering(seeded_tiffin_catalog: TiffinCatalogService) -> None:
    monday = seeded_tiffin_catalog.list_daily_menu('monday')
    breakfast = seeded_tiffin_catalog.list_meals_for_day_and_type('Monday', 'breakfast')
    lunch = seeded_tiffin_catalog.list_meals_for_day_and_type('Monday', 'lunch')
    dinner = seeded_tiffin_catalog.list_meals_for_day_and_type('Monday', 'dinner')

    assert len(monday['breakfast']) == 3
    assert len(breakfast) == 3
    assert len(lunch) == 3
    assert len(dinner) == 3
    assert all(meal.meal_type == 'breakfast' for meal in breakfast)


def test_menu_prices_come_from_database(seeded_tiffin_catalog: TiffinCatalogService) -> None:
    menu = seeded_tiffin_catalog.list_daily_menu('Monday')
    first_breakfast = menu['breakfast'][0]

    assert first_breakfast.name == 'Aloo Paratha with Raita'
    assert first_breakfast.price == Decimal('170.00')
    assert any(meal.name == 'Anda Paratha' and meal.price == Decimal('180.00') for meal in menu['breakfast'])


def test_subscription_plan_retrieval(db_session, seeded_tiffin_catalog: TiffinCatalogService) -> None:
    service = SubscriptionService(db_session)
    plans = service.list_subscription_plans()

    assert len(plans) == 10
    assert plans[0].name == 'Weekly Breakfast Plan'
    plan = service.retrieve_subscription_plan(plans[0].id)
    assert plan is not None
    assert plan.name == 'Weekly Breakfast Plan'
    assert plan.included_meal_types == ['breakfast']


def test_active_customer_subscription_lookup(db_session, seeded_tiffin_catalog: TiffinCatalogService) -> None:
    subscription_service = SubscriptionService(db_session)
    plan = subscription_service.list_subscription_plans()[0]

    subscription_service.create_customer_subscription(
        customer_phone='15551234567',
        subscription_plan_id=plan.id,
        start_date=date(2026, 7, 20),
        end_date=date(2026, 7, 26),
        delivery_address='House 12, Karachi',
        preferred_meal_choices=['Anda Paratha'],
        payment_method='cash_on_delivery',
        status='active',
    )

    active = subscription_service.get_active_subscription('15551234567', on_date=date(2026, 7, 22))
    context = subscription_service.get_customer_subscription_context('15551234567', on_date=date(2026, 7, 22))

    assert active is not None
    assert active.status == 'active'
    assert context['has_active_subscription'] is True
    assert context['status'] == 'active'
    assert context['start_date'] == date(2026, 7, 20)
    assert context['end_date'] == date(2026, 7, 26)
    assert context['included_meals_today'] == ['breakfast']


def test_subscription_does_not_require_daily_confirmation(db_session, seeded_tiffin_catalog: TiffinCatalogService) -> None:
    subscription_service = SubscriptionService(db_session)
    plan = next(plan for plan in subscription_service.list_subscription_plans() if plan.name == 'Weekly Full-Day Plan')

    subscription_service.create_customer_subscription(
        customer_phone='15551230000',
        subscription_plan_id=plan.id,
        start_date=date(2026, 7, 21),
        end_date=date(2026, 7, 27),
        delivery_address='Lahore Office',
        preferred_meal_choices=['Chicken Biryani'],
        payment_method='bank_transfer',
        status='active',
    )

    context = subscription_service.get_customer_subscription_context('15551230000', on_date=date(2026, 7, 22))

    assert context['has_active_subscription'] is True
    assert context['included_meals_today'] == ['breakfast', 'lunch', 'dinner']


def test_valid_meal_skip_more_than_12_hours_before_delivery(db_session, seeded_tiffin_catalog: TiffinCatalogService) -> None:
    subscription_service = SubscriptionService(db_session)
    plan = subscription_service.list_subscription_plans()[0]
    subscription = subscription_service.create_customer_subscription(
        customer_phone='15551234567',
        subscription_plan_id=plan.id,
        start_date=date(2026, 7, 22),
        end_date=date(2026, 7, 28),
        delivery_address='Office 7',
        preferred_meal_choices=['Anda Paratha'],
        payment_method='cash_on_delivery',
        status='active',
    )

    policy = TiffinPolicyService(db_session)
    requested_at = datetime(2026, 7, 21, 18, 0, tzinfo=timezone.utc)
    result = policy.validate_meal_skip(subscription=subscription, meal_date=date(2026, 7, 22), meal_type='breakfast', requested_at=requested_at, reason='Exam')

    assert result.is_valid is True


def test_invalid_meal_skip_within_12_hours(db_session, seeded_tiffin_catalog: TiffinCatalogService) -> None:
    subscription_service = SubscriptionService(db_session)
    plan = subscription_service.list_subscription_plans()[0]
    subscription = subscription_service.create_customer_subscription(
        customer_phone='15551234567',
        subscription_plan_id=plan.id,
        start_date=date(2026, 7, 22),
        end_date=date(2026, 7, 28),
        delivery_address='Office 7',
        preferred_meal_choices=['Anda Paratha'],
        payment_method='cash_on_delivery',
        status='active',
    )

    policy = TiffinPolicyService(db_session)
    requested_at = datetime(2026, 7, 22, 3, 0, tzinfo=timezone.utc)
    result = policy.validate_meal_skip(subscription=subscription, meal_date=date(2026, 7, 22), meal_type='breakfast', requested_at=requested_at, reason='Late meeting')

    assert result.is_valid is False
    assert '12 hours' in (result.reason or '').lower()


def test_valid_bulk_order_more_than_24_hours_before_delivery(db_session) -> None:
    policy = TiffinPolicyService(db_session)
    future_delivery = datetime.now(timezone.utc) + timedelta(hours=25)
    result = policy.validate_bulk_order(requested_delivery_at=future_delivery, number_of_boxes=BULK_ORDER_THRESHOLD)

    assert result.is_valid is True


def test_invalid_bulk_order_within_24_hours(db_session) -> None:
    policy = TiffinPolicyService(db_session)
    soon_delivery = datetime.now(timezone.utc) + timedelta(hours=12)
    result = policy.validate_bulk_order(requested_delivery_at=soon_delivery, number_of_boxes=BULK_ORDER_THRESHOLD)

    assert result.is_valid is False
    assert '24 hours' in (result.reason or '').lower()


def test_supported_payment_methods() -> None:
    assert SUPPORTED_PAYMENT_METHODS == {'cash_on_delivery', 'online_transfer', 'bank_transfer'}


def test_bulk_order_fields_are_persisted(db_session) -> None:
    product_service = ProductService(db_session)
    meal = product_service.create_product(name='Test Meal', description='meal', price=Decimal('250.00'), is_available=True)
    order_service = OrderService(db_session)
    order = order_service.create_draft_order(
        OrderCreate(
            order_number='ORD-BULK-1',
            customer_phone='15550001111',
            delivery_address='Karachi',
            payment_method='online_transfer',
            is_bulk_order=True,
            requested_delivery_at=datetime.now(timezone.utc) + timedelta(hours=30),
            number_of_boxes=10,
            special_instructions='Keep it spicy',
            items=[{'product_id': meal.id, 'quantity': 10}],
        )
    )

    assert order.payment_method == 'online_transfer'
    assert order.is_bulk_order is True
    assert order.number_of_boxes == 10
    assert order.special_instructions == 'Keep it spicy'


def test_invalid_bulk_order_within_24_hours_raises(db_session) -> None:
    product_service = ProductService(db_session)
    meal = product_service.create_product(name='Bulk Meal', description='meal', price=Decimal('250.00'), is_available=True)
    order_service = OrderService(db_session)

    with pytest.raises(ValueError, match='24 hours'):
        order_service.create_draft_order(
            OrderCreate(
                order_number='ORD-BULK-2',
                customer_phone='15550002222',
                delivery_address='Lahore',
                payment_method='cash_on_delivery',
                is_bulk_order=True,
                requested_delivery_at=datetime.now(timezone.utc) + timedelta(hours=6),
                number_of_boxes=10,
                items=[{'product_id': meal.id, 'quantity': 10}],
            )
        )


def test_catalog_seed_is_insert_only_and_idempotent(db_session, seeded_tiffin_catalog: TiffinCatalogService) -> None:
    subscription_service = SubscriptionService(db_session)
    plan = next(plan for plan in subscription_service.list_subscription_plans() if plan.name == 'Weekly Lunch Plan')
    original_description = plan.description
    original_active = plan.is_active

    plan.description = 'Administrator updated description'
    plan.is_active = False
    db_session.commit()

    from app.data.tiffin_seed import seed_tiffin_catalog

    seed_tiffin_catalog(db_session)
    seed_tiffin_catalog(db_session)

    refreshed = subscription_service.retrieve_subscription_plan(plan.id)
    assert refreshed is not None
    assert refreshed.description == 'Administrator updated description'
    assert refreshed.is_active is False
