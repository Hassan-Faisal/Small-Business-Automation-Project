from __future__ import annotations

from datetime import date

import pytest

from app.services.tiffin_service import SubscriptionService


def test_subscription_lifecycle_transitions_and_cancelled_safety(db_session, seeded_tiffin_catalog) -> None:
    service = SubscriptionService(db_session)
    plan = service.list_subscription_plans()[0]
    subscription = service.create_customer_subscription(
        customer_phone='15559990000',
        subscription_plan_id=plan.id,
        start_date=date(2026, 7, 29),
        end_date=date(2026, 8, 4),
        delivery_address='House 9',
        preferred_meal_choices=['Anda Paratha'],
        payment_method='cash_on_delivery',
        status='pending',
    )

    active = service.update_subscription_status(subscription, 'active')
    assert active.status == 'active'

    paused = service.update_subscription_status(active, 'paused')
    assert paused.status == 'paused'

    resumed = service.update_subscription_status(paused, 'active')
    assert resumed.status == 'active'

    cancelled = service.update_subscription_status(resumed, 'cancelled')
    assert cancelled.status == 'cancelled'

    with pytest.raises(ValueError):
        service.update_subscription_status(cancelled, 'active')

    assert service.get_active_subscription('15559990000', on_date=date(2026, 7, 30)) is None
    assert service.get_customer_subscription_context('15559990000', on_date=date(2026, 7, 30))['has_active_subscription'] is False
    assert service.pause_customer_subscription('15559990000') is None
    assert service.resume_customer_subscription('15559990000', on_date=date(2026, 7, 30)) is None
    assert service.cancel_customer_subscription('15559990000') is None
