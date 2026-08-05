from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import pytest

from app.core.config import settings
from app.core.security import hash_password
from app.models.admin_user import AdminUser
from app.models.order import Order
from app.schemas.admin_order import AdminOrderDeliveryUpdate
from app.schemas.order_notification import NotificationResult
from app.services.admin_order_service import AdminOrderInvalidTransitionError, AdminOrderService
from app.services.order_notification_service import OrderNotificationService
from app.services.whatsapp_outbound_provider import MetaWhatsAppOutboundProvider, TwilioWhatsAppOutboundProvider, build_whatsapp_outbound_provider


class FakeOutbound:
    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self.messages: list[dict[str, str]] = []
        self.result = result or {"status": "ok", "data": {"messages": [{"id": "wamid.test-1"}]}}

    async def send_text_message(self, *, recipient_phone: str, text: str) -> dict[str, Any]:
        self.messages.append({"recipient_phone": recipient_phone, "text": text})
        return self.result


class FakeNotifications:
    def __init__(self, result: NotificationResult | None = None) -> None:
        self.status_orders: list[Order] = []
        self.delivery_orders: list[Order] = []
        self.result = result or NotificationResult(status="sent", message_sid="wamid.fake")

    def notify_status(self, order: Order) -> NotificationResult:
        self.status_orders.append(order)
        return self.result

    def notify_delivery_update(self, order: Order) -> NotificationResult:
        self.delivery_orders.append(order)
        return self.result


def make_order(status: str = "confirmed", phone: str = "whatsapp:+923001234567") -> Order:
    return Order(
        id=1,
        order_number="ORD-500",
        customer_phone=phone,
        delivery_address="House 1",
        status=status,
        total_amount=Decimal("100.00"),
        delivery_provider="bykea",
        estimated_delivery_minutes=30,
        internal_note="NEVER SEND THIS",
    )


def add_admin(db_session) -> AdminUser:
    admin = AdminUser(full_name="Owner", email="notifications@example.com", hashed_password=hash_password("StrongPassword1"))
    db_session.add(admin)
    db_session.commit()
    return admin


def add_persisted_order(db_session, status: str = "draft", order_number: str = "ORD-NOTIFY") -> Order:
    order = Order(
        order_number=order_number,
        customer_phone="whatsapp:+923001234567",
        delivery_address="House 1",
        status=status,
        total_amount=Decimal("100.00"),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture()
def configured_whatsapp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "test-access-token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "test-phone-number-id")


def test_status_messages_and_out_for_delivery_context(configured_whatsapp) -> None:
    outbound = FakeOutbound()
    service = OrderNotificationService(outbound_service=outbound)

    for status, expected in {
        "confirmed": "Your order ORD-500 has been confirmed.",
        "preparing": "Your order ORD-500 is now being prepared.",
        "completed": "Your order ORD-500 has been delivered. Thank you for ordering with us.",
        "cancelled": "Your order ORD-500 has been cancelled.",
    }.items():
        order = make_order(status)
        result = service.notify_status(order)
        assert result.status == "sent"
        assert expected in outbound.messages[-1]["text"]

    delivery_order = make_order("out_for_delivery")
    result = service.notify_status(delivery_order)
    assert result.status == "sent"
    message = outbound.messages[-1]["text"]
    assert "out for delivery via bykea" in message
    assert "Estimated arrival: 30 minutes." in message
    assert "rider may call" in message


def test_phone_normalization_and_synthetic_numbers_are_skipped(configured_whatsapp) -> None:
    outbound = FakeOutbound()
    service = OrderNotificationService(outbound_service=outbound)

    result = service.notify_status(make_order(phone="whatsapp:+923001234567"))
    assert result.status == "sent"
    assert outbound.messages[-1]["recipient_phone"] == "923001234567"

    result = service.notify_status(make_order(phone="test:+15550001111"))
    assert result.status == "skipped"
    assert result.reason == "synthetic_test_phone"
    assert len(outbound.messages) == 1


def test_internal_note_never_appears_in_customer_message(configured_whatsapp) -> None:
    outbound = FakeOutbound()
    service = OrderNotificationService(outbound_service=outbound)

    service.notify_status(make_order("preparing"))
    assert "NEVER SEND THIS" not in outbound.messages[-1]["text"]


def test_missing_configuration_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
    outbound = FakeOutbound()
    result = OrderNotificationService(outbound_service=outbound).notify_status(make_order())

    assert result.status == "skipped"
    assert result.reason == "whatsapp_configuration_missing"
    assert outbound.messages == []


def test_provider_failure_returns_failed_without_raising(configured_whatsapp) -> None:
    outbound = FakeOutbound({"status": "error", "status_code": 503})
    result = OrderNotificationService(outbound_service=outbound).notify_status(make_order())

    assert result.status == "failed"
    assert result.reason == "provider_error"


def test_admin_status_update_commits_before_notification_and_failure_does_not_rollback(db_session, configured_whatsapp) -> None:
    admin = add_admin(db_session)
    order = add_persisted_order(db_session)
    notifications = FakeNotifications(NotificationResult(status="failed", reason="provider_error"))
    service = AdminOrderService(db_session, notification_service=notifications)

    response = service.update_status(order.id, "confirmed", admin)

    assert response.status == "confirmed"
    assert notifications.status_orders[0].status == "confirmed"
    db_session.expire_all()
    assert db_session.get(Order, order.id).status == "confirmed"


def test_same_status_is_rejected_without_notification(db_session) -> None:
    admin = add_admin(db_session)
    order = add_persisted_order(db_session, status="confirmed")
    notifications = FakeNotifications()
    service = AdminOrderService(db_session, notification_service=notifications)

    with pytest.raises(AdminOrderInvalidTransitionError):
        service.update_status(order.id, "confirmed", admin)

    assert notifications.status_orders == []


def test_delivery_notification_only_for_relevant_status_and_excludes_notes(db_session) -> None:
    admin = add_admin(db_session)
    order = add_persisted_order(db_session, status="rider_assigned")
    notifications = FakeNotifications()
    service = AdminOrderService(db_session, notification_service=notifications)

    service.update_delivery(
        order.id,
        AdminOrderDeliveryUpdate(estimated_delivery_minutes=45, delivery_provider="yango", internal_note="PRIVATE"),
        admin,
    )
    assert len(notifications.delivery_orders) == 1

    non_delivery_order = add_persisted_order(db_session, status="preparing", order_number="ORD-NOTIFY-2")
    service.update_delivery(
        non_delivery_order.id,
        AdminOrderDeliveryUpdate(estimated_delivery_minutes=20),
        admin,
    )
    assert len(notifications.delivery_orders) == 1


def test_notification_transport_exception_isolated_from_status_update(db_session) -> None:
    admin = add_admin(db_session)
    order = add_persisted_order(db_session)

    class BrokenNotifications:
        def notify_status(self, order: Order) -> NotificationResult:
            raise RuntimeError("provider unavailable")

        def notify_delivery_update(self, order: Order) -> NotificationResult:
            raise RuntimeError("provider unavailable")

    response = AdminOrderService(db_session, notification_service=BrokenNotifications()).update_status(order.id, "confirmed", admin)

    assert response.status == "confirmed"
    db_session.expire_all()
    assert db_session.get(Order, order.id).status == "confirmed"



class FakeTwilioMessages:
    def __init__(self, sid: str = "SM-test-1", error: Exception | None = None) -> None:
        self.calls: list[dict[str, str]] = []
        self.sid = sid
        self.error = error

    def create(self, **kwargs: str):
        if self.error:
            raise self.error
        self.calls.append(kwargs)
        return type("Message", (), {"sid": self.sid})()


class FakeTwilioClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.messages = FakeTwilioMessages(error=error)


def configure_twilio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC-test")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "token-test")
    monkeypatch.setattr(settings, "TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    monkeypatch.setattr(settings, "WHATSAPP_OUTBOUND_PROVIDER", "twilio")


def test_twilio_is_default_and_normalizes_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_twilio(monkeypatch)
    client = FakeTwilioClient()
    provider = TwilioWhatsAppOutboundProvider(client=client)
    result = provider.send_text_message(recipient_phone="whatsapp:+92300 1234567", text="hello")

    assert isinstance(build_whatsapp_outbound_provider(), TwilioWhatsAppOutboundProvider)
    assert result.status == "sent"
    assert result.message_sid == "SM-test-1"
    assert client.messages.calls == [{"body": "hello", "from_": "whatsapp:+14155238886", "to": "whatsapp:+923001234567"}]


def test_twilio_status_messages_use_provider_and_capture_sid(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_twilio(monkeypatch)
    client = FakeTwilioClient()
    service = OrderNotificationService(provider=TwilioWhatsAppOutboundProvider(client=client))

    for status in ("confirmed", "preparing", "out_for_delivery"):
        order = make_order(status)
        result = service.notify_status(order)
        assert result.status == "sent"
        assert result.message_sid == "SM-test-1"
    assert len(client.messages.calls) == 3
    assert "via bykea" in client.messages.calls[-1]["body"]
    assert "30 minutes" in client.messages.calls[-1]["body"]
    assert "NEVER SEND THIS" not in client.messages.calls[-1]["body"]


def test_twilio_failure_is_safe_and_status_remains_committed(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_twilio(monkeypatch)
    admin = add_admin(db_session)
    order = add_persisted_order(db_session)
    provider = TwilioWhatsAppOutboundProvider(client=FakeTwilioClient(error=RuntimeError("twilio down")))
    service = AdminOrderService(db_session, notification_service=OrderNotificationService(provider=provider))

    response = service.update_status(order.id, "confirmed", admin)

    assert response.status == "confirmed"
    db_session.expire_all()
    assert db_session.get(Order, order.id).status == "confirmed"


def test_meta_provider_is_explicit_and_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WHATSAPP_OUTBOUND_PROVIDER", "meta")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "meta-token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "meta-number")
    outbound = FakeOutbound()
    provider = MetaWhatsAppOutboundProvider(outbound_service=outbound)
    result = provider.send_text_message(recipient_phone="923001234567", text="hello")

    assert result.status == "sent"
    assert result.message_sid == "wamid.test-1"
    assert outbound.messages[0]["recipient_phone"] == "923001234567"


def test_missing_twilio_configuration_is_skipped_without_external_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "TWILIO_WHATSAPP_NUMBER", "")
    client = FakeTwilioClient()
    result = TwilioWhatsAppOutboundProvider(client=client).send_text_message(recipient_phone="923001234567", text="hello")

    assert result.status == "skipped"
    assert client.messages.calls == []
