from __future__ import annotations

import asyncio


def _workflow_day_name(workflow) -> str:
    return workflow._message_day('today')


def test_today_menu_uses_database_items(workflow, seeded_tiffin_catalog) -> None:
    result = asyncio.run(
        workflow.run(
            "What is today's menu?",
            conversation_id='menu-today',
            customer_phone='15551234567',
            message_id='menu-today-1',
        )
    )

    today = _workflow_day_name(workflow)
    day_menu = seeded_tiffin_catalog.list_daily_menu(today)

    assert result['intent'] == 'today_menu'
    assert today.lower() in result['response'].lower()
    assert day_menu['breakfast']
    assert day_menu['lunch']
    assert day_menu['dinner']
    assert day_menu['breakfast'][0].name.lower() in result['response'].lower()


def test_weekly_menu_shows_day_selection(workflow, seeded_tiffin_catalog) -> None:
    result = asyncio.run(
        workflow.run(
            'Weekly menu',
            conversation_id='menu-weekly',
            customer_phone='15551234567',
            message_id='menu-weekly-1',
        )
    )

    response = result['response']
    assert result['intent'] == 'weekly_menu'
    assert len(response) < 1500
    assert 'Choose a day' in response
    for index, day in enumerate(('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'), start=1):
        assert f'{index}. {day}' in response


def test_weekly_menu_day_name_returns_selected_day(workflow, seeded_tiffin_catalog) -> None:
    conversation_id = 'menu-weekly-day-name'
    asyncio.run(
        workflow.run(
            'weekly menu',
            conversation_id=conversation_id,
            customer_phone='15551234567',
            message_id='menu-weekly-day-name-1',
        )
    )
    result = asyncio.run(
        workflow.run(
            'Monday',
            conversation_id=conversation_id,
            customer_phone='15551234567',
            message_id='menu-weekly-day-name-2',
        )
    )

    assert 'Monday menu:' in result['response']
    assert 'Anda Paratha' in result['response']
    assert 'Chicken Biryani' in result['response']


def test_weekly_menu_numeric_selection_returns_monday(workflow, seeded_tiffin_catalog) -> None:
    conversation_id = 'menu-weekly-number'
    asyncio.run(
        workflow.run(
            'weekly menu',
            conversation_id=conversation_id,
            customer_phone='15551234567',
            message_id='menu-weekly-number-1',
        )
    )
    result = asyncio.run(
        workflow.run(
            '1',
            conversation_id=conversation_id,
            customer_phone='15551234567',
            message_id='menu-weekly-number-2',
        )
    )

    assert 'Monday menu:' in result['response']
    assert 'Chicken Biryani' in result['response']
def test_breakfast_menu_mentions_breakfast_items(workflow, seeded_tiffin_catalog) -> None:
    result = asyncio.run(
        workflow.run(
            'Breakfast menu',
            conversation_id='menu-breakfast',
            customer_phone='15551234567',
            message_id='menu-breakfast-1',
        )
    )

    today = _workflow_day_name(workflow)
    breakfast_items = seeded_tiffin_catalog.list_daily_menu(today)['breakfast']

    assert result['intent'] == 'breakfast_menu'
    assert 'breakfast' in result['response'].lower()
    assert breakfast_items[0].name.lower() in result['response'].lower()
    assert 'lunch:' not in result['response'].lower()


def test_lunch_menu_mentions_lunch_items(workflow, seeded_tiffin_catalog) -> None:
    result = asyncio.run(
        workflow.run(
            'Lunch',
            conversation_id='menu-lunch',
            customer_phone='15551234567',
            message_id='menu-lunch-1',
        )
    )

    today = _workflow_day_name(workflow)
    lunch_items = seeded_tiffin_catalog.list_daily_menu(today)['lunch']

    assert result['intent'] == 'lunch_menu'
    assert 'lunch' in result['response'].lower()
    assert lunch_items[0].name.lower() in result['response'].lower()
    assert 'breakfast:' not in result['response'].lower()


def test_dinner_menu_mentions_dinner_items(workflow, seeded_tiffin_catalog) -> None:
    result = asyncio.run(
        workflow.run(
            'Dinner',
            conversation_id='menu-dinner',
            customer_phone='15551234567',
            message_id='menu-dinner-1',
        )
    )

    today = _workflow_day_name(workflow)
    dinner_items = seeded_tiffin_catalog.list_daily_menu(today)['dinner']

    assert result['intent'] == 'dinner_menu'
    assert 'dinner' in result['response'].lower()
    assert dinner_items[0].name.lower() in result['response'].lower()
    assert 'breakfast:' not in result['response'].lower()


def test_roman_urdu_menu_phrases_are_supported(workflow, seeded_tiffin_catalog) -> None:
    result = asyncio.run(
        workflow.run(
            'Aaj breakfast mein kya hai?',
            conversation_id='menu-roman-urdu',
            customer_phone='15551234567',
            message_id='menu-roman-urdu-1',
        )
    )

    today = _workflow_day_name(workflow)
    breakfast_items = seeded_tiffin_catalog.list_daily_menu(today)['breakfast']

    assert result['intent'] == 'breakfast_menu'
    assert breakfast_items[0].name.lower() in result['response'].lower()


def test_address_only_message_is_accepted_during_checkout(workflow) -> None:
    conversation_id = 'menu-address-flow'
    customer_phone = '15551234567'

    asyncio.run(
        workflow.run(
            'Add Chicken Biryani',
            conversation_id=conversation_id,
            customer_phone=customer_phone,
            message_id='menu-address-1',
        )
    )

    address_result = asyncio.run(
        workflow.run(
            'House 12, Street 4, Islamabad',
            conversation_id=conversation_id,
            customer_phone=customer_phone,
            message_id='menu-address-2',
        )
    )

    confirm_result = asyncio.run(
        workflow.run(
            'Confirm order',
            conversation_id=conversation_id,
            customer_phone=customer_phone,
            message_id='menu-address-3',
        )
    )

    assert address_result['intent'] == 'provide_address'
    assert 'saved your delivery address' in address_result['response'].lower()
    assert 'placed successfully' in confirm_result['response'].lower()
    assert 'order number:' in confirm_result['response'].lower()
