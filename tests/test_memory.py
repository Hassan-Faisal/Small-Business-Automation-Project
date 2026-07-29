from __future__ import annotations

from app.langgraph.memory import ConversationMemory


def test_memory_persists_cart_and_messages(db_session):
    memory = ConversationMemory(db_session)

    assert memory.get('conv-1')['cart'] == []

    memory.save('conv-1', cart=[{'product_id': 1, 'name': 'Burger', 'quantity': 2, 'unit_price': '10.00'}], customer_phone='15551234567')
    memory.save('conv-1', messages=[{'role': 'user', 'content': 'hello'}])
    memory.mark_processed_message('conv-1', 'msg-1')

    loaded = memory.get('conv-1')
    assert loaded['customer_phone'] == '15551234567'
    assert loaded['cart'][0]['name'] == 'Burger'
    assert loaded['messages'][0]['content'] == 'hello'
    assert memory.has_processed_message('conv-1', 'msg-1') is True


def test_memory_clear_removes_state(db_session):
    memory = ConversationMemory(db_session)
    memory.save('conv-1', cart=[{'product_id': 1}], customer_phone='15551234567')

    memory.clear('conv-1')

    assert memory.get('conv-1')['cart'] == []
