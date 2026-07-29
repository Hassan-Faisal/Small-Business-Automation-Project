from __future__ import annotations

import asyncio


def test_customer_journey_and_idempotency(workflow, seeded_products, conversation_id, customer_phone, message_ids, fake_rag_chain):
    greeting = asyncio.run(workflow.run('Hello', conversation_id=conversation_id, customer_phone=customer_phone, message_id=message_ids['hello']))
    assert 'hello' in greeting['response'].lower()

    menu = asyncio.run(workflow.run('Show me the menu', conversation_id=conversation_id, customer_phone=customer_phone, message_id=message_ids['menu']))
    assert 'monday' in menu['retrieved_context'].lower()
    assert 'anda paratha' in menu['retrieved_context'].lower()
    assert 'chicken biryani' in menu['retrieved_context'].lower()

    add_burger = asyncio.run(workflow.run('Add 2 Burgers', conversation_id=conversation_id, customer_phone=customer_phone, message_id=message_ids['add_burger']))
    assert add_burger['cart'][0]['quantity'] == 2

    duplicate_add = asyncio.run(workflow.run('Add 2 Burgers', conversation_id=conversation_id, customer_phone=customer_phone, message_id=message_ids['add_burger']))
    assert duplicate_add['cart'][0]['quantity'] == 2

    view_cart = asyncio.run(workflow.run('View cart', conversation_id=conversation_id, customer_phone=customer_phone, message_id=message_ids['view_cart']))
    assert 'Burger' in view_cart['response']
    assert 'Quantity' not in view_cart['response']

    remove_item = asyncio.run(workflow.run('Remove Burger', conversation_id=conversation_id, customer_phone=customer_phone, message_id='msg-remove'))
    assert 'removed' in remove_item['response'].lower()

    empty_cart = asyncio.run(workflow.run('View cart', conversation_id='conv-empty', customer_phone=customer_phone, message_id='msg-empty-view'))
    assert 'empty' in empty_cart['response'].lower()

    unknown_product = asyncio.run(workflow.run('Add 1 Taco', conversation_id=conversation_id, customer_phone=customer_phone, message_id='msg-unknown'))
    assert 'couldn' in unknown_product['response'].lower()

    zero_quantity = asyncio.run(workflow.run('Add 0 Burger', conversation_id=conversation_id, customer_phone=customer_phone, message_id='msg-zero'))
    assert 'greater than zero' in zero_quantity['response'].lower()

    negative_quantity = asyncio.run(workflow.run('Add -2 Burger', conversation_id=conversation_id, customer_phone=customer_phone, message_id='msg-negative'))
    assert 'greater than zero' in negative_quantity['response'].lower()

    conversation_two = asyncio.run(workflow.run('View cart', conversation_id='conv-2', customer_phone='15550000000', message_id='msg-conv-2'))
    assert 'empty' in conversation_two['response'].lower()

    address = asyncio.run(workflow.run('I live at 123 Main St', conversation_id=conversation_id, customer_phone=customer_phone, message_id=message_ids['address']))
    assert address['address'] == 'I live at 123 Main St'

    asyncio.run(workflow.run('Add 1 Burger', conversation_id=conversation_id, customer_phone=customer_phone, message_id='msg-readd'))

    asyncio.run(workflow.run('Add 1 Burger', conversation_id='conv-no-address', customer_phone=customer_phone, message_id='msg-no-address-add'))
    confirm_without_address = asyncio.run(workflow.run('Confirm my order', conversation_id='conv-no-address', customer_phone=customer_phone, message_id='msg-no-address'))
    assert 'address' in confirm_without_address['response'].lower()

    policy = asyncio.run(workflow.run('What is your delivery policy?', conversation_id=conversation_id, customer_phone=customer_phone, message_id=message_ids['policy']))
    assert policy['response'] == fake_rag_chain.response
    assert fake_rag_chain.calls

    confirm = asyncio.run(workflow.run('Confirm my order', conversation_id=conversation_id, customer_phone=customer_phone, message_id=message_ids['confirm']))
    assert confirm['order_number'].startswith('ORD-')
    assert confirm['order_status'] == 'confirmed'

    duplicate_confirm = asyncio.run(workflow.run('Confirm my order', conversation_id=conversation_id, customer_phone=customer_phone, message_id=message_ids['confirm']))
    assert duplicate_confirm['order_number'] == confirm['order_number']
    assert duplicate_confirm['order_status'] == 'confirmed'

    explicit_track = asyncio.run(workflow.run(f'What is the status of order {confirm["order_number"]}?', conversation_id=conversation_id, customer_phone=customer_phone, message_id=message_ids['track']))
    assert explicit_track['order_status'] == 'confirmed'
    assert confirm['order_number'] in explicit_track['response']

    remembered_track = asyncio.run(workflow.run('What is my order status?', conversation_id=conversation_id, customer_phone=customer_phone, message_id='msg-track-remembered'))
    assert remembered_track['order_status'] == 'confirmed'

    unknown_order = asyncio.run(workflow.run('What is the status of order ORD-UNKNOWN?', conversation_id=conversation_id, customer_phone=customer_phone, message_id='msg-track-unknown'))
    assert 'couldn' in unknown_order['response'].lower()

    fallback = asyncio.run(workflow.run('Tell me something unrelated', conversation_id=conversation_id, customer_phone=customer_phone, message_id='msg-fallback'))
    assert 'policy response' not in fallback['response'].lower()

    state = workflow.memory.get(conversation_id)
    assert state['customer_phone'] == customer_phone
    assert len(state['messages']) >= 2

def test_rag_dict_response_is_normalized_to_text(workflow, conversation_id, customer_phone) -> None:
    class DictRAGChain:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def ask(self, message: str):
            self.calls.append(message)
            return {"response": "We deliver across Lahore"}

    workflow.rag_chain = DictRAGChain()  # type: ignore[assignment]

    result = asyncio.run(
        workflow.run(
            'Where do you deliver?',
            conversation_id=conversation_id,
            customer_phone=customer_phone,
            message_id='msg-rag-dict',
        )
    )

    assert result['intent'] == 'delivery_area'
    assert result['response'] == 'We deliver across Lahore'
    assert workflow.rag_chain.calls == ['Where do you deliver?']



def test_menu_option_selection_and_subscription_plan_journey(workflow, seeded_products, customer_phone) -> None:
    conversation_id = 'journey-guided'

    menu = asyncio.run(
        workflow.run(
            'Show me the menu',
            conversation_id=conversation_id,
            customer_phone=customer_phone,
            message_id='journey-menu',
        )
    )
    assert menu['intent'] in {'weekly_menu', 'today_menu', 'menu'}
    assert 'anda paratha' in menu['response'].lower()

    add_item = asyncio.run(
        workflow.run(
            'Add 1 Burger',
            conversation_id=conversation_id,
            customer_phone=customer_phone,
            message_id='journey-add-item',
        )
    )
    assert add_item['cart']
    assert add_item['cart'][0]['quantity'] == 1

    plans = asyncio.run(
        workflow.run(
            'Weekly subscription plans',
            conversation_id=conversation_id,
            customer_phone=customer_phone,
            message_id='journey-plans',
        )
    )
    assert 'Available plans' in plans['response']
    assert plans['intent'] == 'subscription_plans'

    subscription = asyncio.run(
        workflow.run(
            'Weekly Full-Day Plan',
            conversation_id=conversation_id,
            customer_phone=customer_phone,
            message_id='journey-plan-select',
        )
    )
    assert 'delivery address' in subscription['response'].lower()
    assert subscription['intent'] in {'create_subscription', 'subscribe'}
