from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import settings
from app.services.whatsapp_service import WhatsAppOutboundService, WhatsAppWebhookService


class FakeChatService:
    def __init__(self, response: str = 'echo:Hello there') -> None:
        self.response = response
        self.calls: list[dict[str, str | None]] = []

    async def chat(self, message: str, conversation_id: str | None = None, customer_phone: str | None = None, message_id: str | None = None) -> str:
        self.calls.append({
            'message': message,
            'conversation_id': conversation_id,
            'customer_phone': customer_phone,
            'message_id': message_id,
        })
        return self.response


class FakeOutboundService:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def send_text_message(self, recipient_phone: str, text: str):
        self.messages.append({'recipient_phone': recipient_phone, 'text': text})
        return {'status': 'ok'}


@pytest.fixture()
def meta_settings(monkeypatch):
    monkeypatch.setattr(settings, 'WHATSAPP_VERIFY_TOKEN', 'verify-me')
    monkeypatch.setattr(settings, 'WHATSAPP_ACCESS_TOKEN', 'access-token')
    monkeypatch.setattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '123456789')
    monkeypatch.setattr(settings, 'WHATSAPP_API_VERSION', 'v21.0')
    monkeypatch.setattr(settings, 'WHATSAPP_WEBHOOK_SECRET', '')


def text_payload(message_id: str = 'msg-1', body: str = 'Hello there', sender: str = '15551234567') -> dict[str, object]:
    return {
        'entry': [
            {
                'changes': [
                    {
                        'value': {
                            'messages': [
                                {
                                    'id': message_id,
                                    'from': sender,
                                    'type': 'text',
                                    'text': {'body': body},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


def test_get_webhook_verification_success(meta_settings):
    service = WhatsAppWebhookService(chat_service=None)

    status_code, challenge = service.verify_webhook('subscribe', 'verify-me', 'challenge-123')

    assert status_code == 200
    assert challenge == 'challenge-123'


def test_get_webhook_verification_failure(meta_settings):
    service = WhatsAppWebhookService(chat_service=None)

    status_code, challenge = service.verify_webhook('subscribe', 'wrong-token', 'challenge-123')

    assert status_code == 403
    assert challenge == 'Verification failed'


def test_valid_incoming_text_message_routes_and_replies(meta_settings):
    chat_service = FakeChatService(response='Thanks!')
    outbound_service = FakeOutboundService()
    service = WhatsAppWebhookService(chat_service=chat_service, outbound_service=outbound_service)

    result = asyncio.run(service.handle_webhook(text_payload()))

    assert result['status'] == 'ok'
    assert result['message_id'] == 'msg-1'
    assert result['sender_phone'] == '15551234567'
    assert chat_service.calls == [{
        'message': 'Hello there',
        'conversation_id': '15551234567',
        'customer_phone': '15551234567',
        'message_id': 'msg-1',
    }]
    assert outbound_service.messages == [{'recipient_phone': '15551234567', 'text': 'Thanks!'}]


def test_provider_message_id_blocks_duplicate_cart_updates(meta_settings):
    chat_service = FakeChatService(response='Added 2 x Burger to your cart.')
    outbound_service = FakeOutboundService()
    service = WhatsAppWebhookService(chat_service=chat_service, outbound_service=outbound_service)

    payload = text_payload(message_id='dup-1', body='Add 2 burgers')

    first = asyncio.run(service.handle_webhook(payload))
    second = asyncio.run(service.handle_webhook(payload))

    assert first['status'] == 'ok'
    assert second['status'] == 'duplicate'
    assert len(chat_service.calls) == 1
    assert len(outbound_service.messages) == 1


def test_malformed_payload_is_ignored(meta_settings):
    service = WhatsAppWebhookService(chat_service=FakeChatService(), outbound_service=FakeOutboundService())

    result = asyncio.run(service.handle_webhook({'bad': 'payload'}))

    assert result['status'] == 'ignored'


def test_status_only_event_is_ignored(meta_settings):
    service = WhatsAppWebhookService(chat_service=FakeChatService(), outbound_service=FakeOutboundService())

    result = asyncio.run(service.handle_webhook({'entry': [{'changes': [{'value': {'statuses': [{'id': 'status-1'}]}}]}]}))

    assert result['status'] == 'ignored'


def test_unsupported_message_type_is_ignored(meta_settings):
    service = WhatsAppWebhookService(chat_service=FakeChatService(), outbound_service=FakeOutboundService())

    payload = {
        'entry': [
            {
                'changes': [
                    {
                        'value': {
                            'messages': [
                                {
                                    'id': 'img-1',
                                    'from': '15551234567',
                                    'type': 'image',
                                    'image': {'caption': 'burger'},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    result = asyncio.run(service.handle_webhook(payload))

    assert result['status'] == 'ignored'


def test_outbound_client_success(monkeypatch, meta_settings):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {'messages': [{'id': 'wamid-1'}]}

    class FakeClient:
        def __init__(self) -> None:
            self.requests = []

        async def post(self, url, headers=None, json=None):
            self.requests.append({'url': url, 'headers': headers, 'json': json})
            return FakeResponse()

    client = FakeClient()
    service = WhatsAppOutboundService(client=client)

    result = asyncio.run(service.send_text_message('15551234567', 'Hello'))

    assert result['status'] == 'ok'
    assert client.requests[0]['url'].endswith('/messages')
    assert client.requests[0]['json']['text']['body'] == 'Hello'


def test_outbound_client_http_error(monkeypatch, meta_settings):
    class FakeResponse:
        status_code = 400
        text = 'bad request'

        def raise_for_status(self) -> None:
            request = httpx.Request('POST', 'https://example.test/messages')
            raise httpx.HTTPStatusError('bad request', request=request, response=httpx.Response(400, request=request, text='bad request'))

    class FakeClient:
        async def post(self, url, headers=None, json=None):
            return FakeResponse()

    service = WhatsAppOutboundService(client=FakeClient())

    result = asyncio.run(service.send_text_message('15551234567', 'Hello'))

    assert result['status'] == 'error'
    assert result['status_code'] == 400


def test_outbound_client_timeout(monkeypatch, meta_settings):
    class FakeClient:
        async def post(self, url, headers=None, json=None):
            raise httpx.TimeoutException('timeout', request=httpx.Request('POST', 'https://example.test/messages'))

    service = WhatsAppOutboundService(client=FakeClient())

    result = asyncio.run(service.send_text_message('15551234567', 'Hello'))

    assert result['status'] == 'timeout'


def test_workflow_response_is_passed_to_outbound_client(meta_settings):
    chat_service = FakeChatService(response='workflow reply')
    outbound_service = FakeOutboundService()
    service = WhatsAppWebhookService(chat_service=chat_service, outbound_service=outbound_service)

    result = asyncio.run(service.handle_webhook(text_payload(message_id='msg-outbound', body='Hello')))

    assert result['status'] == 'ok'
    assert outbound_service.messages == [{'recipient_phone': '15551234567', 'text': 'workflow reply'}]
