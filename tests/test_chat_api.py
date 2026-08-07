from __future__ import annotations

from app.langgraph.memory import ConversationMemory
from app.langgraph.workflow import OrderConversationWorkflow
from app.rag.rag_chain import RAGChain
from app.services.chat_service import ChatService


def test_chat_endpoint_uses_customer_phone_and_session(client):
    test_client, chat_service = client

    response = test_client.post(
        '/chat',
        json={
            'message': 'Hello',
            'conversation_id': 'conv-api',
            'customer_phone': '15551234567',
            'message_id': 'api-1',
        },
    )

    assert response.status_code == 200
    assert 'welcome to tiffinai' in response.json()['response'].lower()

    state = chat_service.workflow.memory.get('conv-api')
    assert state['customer_phone'] == '15551234567'
