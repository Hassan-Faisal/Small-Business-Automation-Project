from __future__ import annotations

def test_webhook_get_verification_success(client, monkeypatch):
    test_client, _ = client

    from app.core.config import settings

    monkeypatch.setattr(settings, 'WHATSAPP_VERIFY_TOKEN', 'verify-me')

    response = test_client.get(
        '/webhook',
        params={
            'hub.mode': 'subscribe',
            'hub.verify_token': 'verify-me',
            'hub.challenge': 'challenge-123',
        },
    )

    assert response.status_code == 200
    assert response.text == 'challenge-123'


def test_webhook_get_verification_failure(client, monkeypatch):
    test_client, _ = client

    from app.core.config import settings

    monkeypatch.setattr(settings, 'WHATSAPP_VERIFY_TOKEN', 'verify-me')

    response = test_client.get(
        '/webhook',
        params={
            'hub.mode': 'subscribe',
            'hub.verify_token': 'wrong-token',
            'hub.challenge': 'challenge-123',
        },
    )

    assert response.status_code == 403


def test_webhook_post_valid_text_routes_to_chat_and_preserves_phone(client):
    test_client, chat_service = client

    response = test_client.post(
        '/webhook',
        json={
            'entry': [
                {
                    'changes': [
                        {
                            'value': {
                                'messages': [
                                    {
                                        'id': 'msg-1',
                                        'from': '15551234567',
                                        'timestamp': '1710000000',
                                        'type': 'text',
                                        'text': {'body': 'Hello'},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'
    assert response.json()['sender_phone'] == '15551234567'

    state = chat_service.workflow.memory.get('15551234567')
    assert state['customer_phone'] == '15551234567'


def test_webhook_post_duplicate_message_id_is_idempotent(client):
    test_client, chat_service = client

    payload = {
        'entry': [
            {
                'changes': [
                    {
                        'value': {
                            'messages': [
                                {
                                    'id': 'msg-dup',
                                    'from': '15551234567',
                                    'type': 'text',
                                    'text': {'body': 'Add 2 burgers'},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    first = test_client.post('/webhook', json=payload)
    second = test_client.post('/webhook', json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()['status'] == 'duplicate'

    state = chat_service.workflow.memory.get('15551234567')
    assert len(state['cart']) == 1
