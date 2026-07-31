from __future__ import annotations

import asyncio
from datetime import date, timedelta

from app.langgraph.parsing import CANONICAL_INTENTS, infer_intent
from app.services.tiffin_service import SubscriptionService


def run_message(workflow, message: str, *, conversation_id: str, customer_phone: str, message_id: str):
    return asyncio.run(
        workflow.run(
            message,
            conversation_id=conversation_id,
            customer_phone=customer_phone,
            message_id=message_id,
        )
    )


def test_greeting_menu_cart_order_and_tracking_flow(workflow, customer_phone, fake_rag_chain) -> None:
    greeting = run_message(workflow, 'Assalam o Alaikum', conversation_id='demo-1', customer_phone=customer_phone, message_id='m1')
    assert 'welcome to tiffinai' in greeting['response'].lower()
    assert 'menu' in greeting['response'].lower()

    today_menu = run_message(workflow, "What is available today?", conversation_id='demo-1', customer_phone=customer_phone, message_id='m2')
    assert today_menu['intent'] == 'today_menu'
    assert 'menu:' in today_menu['response'].lower()
    assert 'rs.' in today_menu['response'].lower()

    weekly_menu = run_message(workflow, 'Weekly menu', conversation_id='demo-2', customer_phone=customer_phone, message_id='m3')
    assert weekly_menu['intent'] == 'weekly_menu'
    assert 'monday' in weekly_menu['response'].lower()
    assert 'chicken biryani' in weekly_menu['response'].lower()

    lunch_menu = run_message(workflow, 'Lunch menu', conversation_id='demo-3', customer_phone=customer_phone, message_id='m4')
    assert lunch_menu['intent'] == 'lunch_menu'
    assert 'lunch menu' in lunch_menu['response'].lower()

    add_item = run_message(workflow, 'Add 2 Chicken Biryani', conversation_id='demo-4', customer_phone=customer_phone, message_id='m5')
    assert add_item['intent'] == 'add_item'
    assert 'added 2 x chicken biryani' in add_item['response'].lower()
    assert add_item['cart'][0]['quantity'] == 2

    duplicate = run_message(workflow, 'Add 2 Chicken Biryani', conversation_id='demo-4', customer_phone=customer_phone, message_id='m5')
    assert duplicate['response'] == add_item['response']

    unknown = run_message(workflow, 'Add 1 Sushi Platter', conversation_id='demo-5', customer_phone=customer_phone, message_id='m6')
    assert 'could not find that meal' in unknown['response'].lower()

    empty_cart = run_message(workflow, 'View cart', conversation_id='demo-empty', customer_phone=customer_phone, message_id='m7')
    assert 'cart is empty' in empty_cart['response'].lower()

    view_cart = run_message(workflow, 'View cart', conversation_id='demo-4', customer_phone=customer_phone, message_id='m8')
    assert 'your cart' in view_cart['response'].lower()
    assert 'total:' in view_cart['response'].lower()

    removed = run_message(workflow, 'Remove one Chicken Biryani', conversation_id='demo-4', customer_phone=customer_phone, message_id='m9')
    assert 'removed 1 x chicken biryani' in removed['response'].lower()

    missing_address = run_message(workflow, 'Confirm order', conversation_id='demo-4', customer_phone=customer_phone, message_id='m10')
    assert 'delivery address' in missing_address['response'].lower()

    address = run_message(workflow, 'My address is House 12, Street 4, Islamabad', conversation_id='demo-4', customer_phone=customer_phone, message_id='m11')
    assert 'saved your delivery address' in address['response'].lower()

    confirmed = run_message(workflow, 'Confirm order', conversation_id='demo-4', customer_phone=customer_phone, message_id='m12')
    assert 'order number:' in confirmed['response'].lower()
    assert confirmed['order_number'].startswith('ORD-')
    assert confirmed['order_status'] == 'confirmed'

    tracked = run_message(workflow, 'Track my order', conversation_id='demo-4', customer_phone=customer_phone, message_id='m13')
    assert confirmed['order_number'] in tracked['response']
    assert 'status: confirmed' in tracked['response'].lower()

    cancelled = run_message(workflow, f'Cancel order {confirmed["order_number"]}', conversation_id='demo-4', customer_phone=customer_phone, message_id='m14')
    assert 'has been cancelled' in cancelled['response'].lower()

    delivery_area = run_message(workflow, 'Where do you deliver?', conversation_id='demo-6', customer_phone=customer_phone, message_id='m15')
    assert delivery_area['intent'] == 'delivery_area'
    assert delivery_area['response'] == fake_rag_chain.response

    refund_policy = run_message(workflow, 'What is your refund policy?', conversation_id='demo-7', customer_phone=customer_phone, message_id='m16')
    assert refund_policy['intent'] == 'faq'
    assert refund_policy['response'] == fake_rag_chain.response

    handoff = run_message(workflow, 'Talk to a person about my order', conversation_id='demo-8', customer_phone=customer_phone, message_id='m17')
    assert handoff['intent'] == 'human_handoff'
    assert 'cannot connect you to a live agent' in handoff['response'].lower()

    fallback = run_message(workflow, 'random text that means nothing', conversation_id='demo-9', customer_phone=customer_phone, message_id='m18')
    assert fallback['intent'] == 'fallback'
    assert fallback['response'].strip()


def test_subscription_flows(workflow, db_session, customer_phone) -> None:
    plans = run_message(workflow, 'Subscription plans', conversation_id='sub-1', customer_phone=customer_phone, message_id='s1')
    assert plans['intent'] == 'subscription_plans'
    assert 'available subscription plans' in plans['response'].lower()

    created = run_message(workflow, 'Weekly Lunch Plan', conversation_id='sub-1', customer_phone=customer_phone, message_id='s2')
    assert created['intent'] == 'create_subscription'
    assert 'selected plan: weekly lunch plan' in created['response'].lower()

    status_pending = run_message(workflow, 'Subscription status', conversation_id='sub-1', customer_phone=customer_phone, message_id='s3')
    assert 'status: pending' in status_pending['response'].lower()

    address = run_message(workflow, 'Deliver to DHA Phase 2', conversation_id='sub-1', customer_phone=customer_phone, message_id='s4')
    assert 'pending subscription' in address['response'].lower()

    activated = run_message(workflow, 'Confirm', conversation_id='sub-1', customer_phone=customer_phone, message_id='s5')
    assert 'is now active' in activated['response'].lower()

    paused = run_message(workflow, 'Pause my subscription', conversation_id='sub-1', customer_phone=customer_phone, message_id='s6')
    assert 'paused' in paused['response'].lower()

    resumed = run_message(workflow, 'Resume my subscription', conversation_id='sub-1', customer_phone=customer_phone, message_id='s7')
    assert 'resumed' in resumed['response'].lower()

    skipped = run_message(workflow, 'Skip tomorrow lunch', conversation_id='sub-1', customer_phone=customer_phone, message_id='s8')
    assert 'has been skipped' in skipped['response'].lower() or 'must be requested at least' in skipped['response'].lower()

    cancelled = run_message(workflow, 'Cancel my subscription', conversation_id='sub-1', customer_phone=customer_phone, message_id='s9')
    assert 'cancelled' in cancelled['response'].lower()

    blocked_resume = run_message(workflow, 'Resume my subscription', conversation_id='sub-1', customer_phone=customer_phone, message_id='s10')
    assert 'cannot be resumed' in blocked_resume['response'].lower() or 'do not have a paused subscription' in blocked_resume['response'].lower()


def test_every_canonical_intent_is_reachable_and_non_empty(workflow, customer_phone) -> None:
    samples = {
        'greeting': 'Hello',
        'today_menu': "What is today's menu?",
        'weekly_menu': 'Weekly menu',
        'breakfast_menu': 'Breakfast menu',
        'lunch_menu': 'Lunch menu',
        'dinner_menu': 'Dinner menu',
        'add_item': 'Add 1 Chicken Biryani',
        'remove_item': 'Remove Chicken Biryani',
        'view_cart': 'View cart',
        'provide_address': 'I live at 12 Canal Road',
        'confirm_order': 'Confirm order',
        'track_order': 'Track order ORD-1234',
        'cancel_order': 'Cancel order ORD-1234',
        'subscription_plans': 'Subscription plans',
        'create_subscription': 'Weekly Full-Day Plan',
        'subscription_status': 'Show my subscription',
        'pause_subscription': 'Pause my subscription',
        'resume_subscription': 'Resume my subscription',
        'cancel_subscription': 'Cancel my subscription',
        'skip_meal': 'Skip tomorrow breakfast',
        'bulk_order': 'Need 10 boxes tomorrow',
        'delivery_area': 'Where do you deliver?',
        'delivery_timing': 'What time do you deliver?',
        'payment_methods': 'How can I pay?',
        'faq': 'What are your hours?',
        'human_handoff': 'Human please',
        'fallback': 'nonsense words here',
    }
    seen: set[str] = set()
    for index, (intent, message) in enumerate(samples.items(), start=1):
        result = run_message(workflow, message, conversation_id=f'canon-{index}', customer_phone=customer_phone, message_id=f'c{index}')
        assert infer_intent(message) == intent
        assert result['intent'] == intent
        assert isinstance(result['response'], str) and result['response'].strip()
        seen.add(result['intent'])
    assert seen == set(CANONICAL_INTENTS)


def test_subscription_service_rejects_cancelled_subscription_actions(db_session, seeded_tiffin_catalog) -> None:
    service = SubscriptionService(db_session)
    plan = service.list_subscription_plans()[0]
    subscription = service.create_customer_subscription(
        customer_phone='15550001111',
        subscription_plan_id=plan.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=plan.number_of_days - 1),
        delivery_address='House 9',
        preferred_meal_choices=['Anda Paratha'],
        payment_method='cash_on_delivery',
        status='pending',
    )
    active = service.update_subscription_status(subscription, 'active')
    cancelled = service.update_subscription_status(active, 'cancelled')
    assert cancelled.status == 'cancelled'
    assert service.pause_customer_subscription('15550001111') is None
    assert service.resume_customer_subscription('15550001111', on_date=date.today()) is None
    assert service.cancel_customer_subscription('15550001111') is None
