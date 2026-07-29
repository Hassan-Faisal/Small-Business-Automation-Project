import asyncio
from types import SimpleNamespace

from app.services.whatsapp_service import WhatsAppWebhookService


class FakeChatService:
    def __init__(self):
        self.calls = []

    async def chat(self, message: str, conversation_id: str | None = None, message_id: str | None = None) -> str:
        self.calls.append({"message": message, "conversation_id": conversation_id, "message_id": message_id})
        return f"echo:{message}"


class FakeWhatsAppService:
    def __init__(self):
        self.messages = []

    async def send_text_message(self, recipient_phone: str, text: str) -> None:
        self.messages.append({"recipient_phone": recipient_phone, "text": text})


def test_process_inbound_text_message_extracts_sender_and_body():
    chat_service = FakeChatService()
    outbound_service = FakeWhatsAppService()
    service = WhatsAppWebhookService(chat_service=chat_service, outbound_service=outbound_service)

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "msg-1",
                                    "from": "15551234567",
                                    "type": "text",
                                    "text": {"body": "Hello there"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    result = asyncio.run(service.handle_webhook(payload))

    assert result["status"] == "ok"
    assert chat_service.calls == [{"message": "Hello there", "conversation_id": "15551234567", "message_id": "msg-1"}]
    assert outbound_service.messages == [{"recipient_phone": "15551234567", "text": "echo:Hello there"}]


def test_unsupported_events_are_ignored_without_crashing():
    chat_service = FakeChatService()
    outbound_service = FakeWhatsAppService()
    service = WhatsAppWebhookService(chat_service=chat_service, outbound_service=outbound_service)

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [{"id": "status-1"}]
                        }
                    }
                ]
            }
        ]
    }

    result = asyncio.run(service.handle_webhook(payload))

    assert result["status"] == "ignored"
    assert chat_service.calls == []
    assert outbound_service.messages == []


def test_duplicate_deliveries_do_not_replay_chat():
    chat_service = FakeChatService()
    outbound_service = FakeWhatsAppService()
    service = WhatsAppWebhookService(chat_service=chat_service, outbound_service=outbound_service)

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "dup-1",
                                    "from": "15551234567",
                                    "type": "text",
                                    "text": {"body": "Confirm my order"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    first = asyncio.run(service.handle_webhook(payload))
    second = asyncio.run(service.handle_webhook(payload))

    assert first["status"] == "ok"
    assert second["status"] == "duplicate"
    assert len(chat_service.calls) == 1
    assert len(outbound_service.messages) == 1
