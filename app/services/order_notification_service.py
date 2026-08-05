from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable

from app.models.order import Order
from app.schemas.order_notification import NotificationResult
from app.services.whatsapp_outbound_provider import MetaWhatsAppOutboundProvider, WhatsAppOutboundProvider, build_whatsapp_outbound_provider
from app.services.whatsapp_transport import WhatsAppOutboundService

logger = logging.getLogger(__name__)

_STATUS_MESSAGES: dict[str, str] = {
    "confirmed": "Your order {order_number} has been confirmed.",
    "preparing": "Your order {order_number} is now being prepared.",
    "ready": "Your order {order_number} is ready for pickup by the rider.",
    "rider_assigned": "A rider has been assigned to your order {order_number}.",
    "out_for_delivery": "Your order {order_number} is out for delivery.",
    "completed": "Your order {order_number} has been delivered. Thank you for ordering with us.",
    "cancelled": "Your order {order_number} has been cancelled.",
}
_PHONE_PATTERN = re.compile(r"^\+?\d{8,15}$")


class OrderNotificationService:
    def __init__(
        self,
        provider: WhatsAppOutboundProvider | None = None,
        *,
        outbound_service: WhatsAppOutboundService | None = None,
        send_runner: Callable[[Awaitable[dict[str, Any]]], dict[str, Any]] | None = None,
    ) -> None:
        if provider is not None:
            self.provider = provider
        elif outbound_service is not None:
            self.provider = MetaWhatsAppOutboundProvider(outbound_service, send_runner=send_runner)
        else:
            self.provider = build_whatsapp_outbound_provider()
    @staticmethod
    def _run_send(awaitable: Awaitable[dict[str, Any]]) -> dict[str, Any]:
        return asyncio.run(awaitable)

    @staticmethod
    def normalize_phone(raw_phone: str) -> tuple[str | None, str | None]:
        value = raw_phone.strip()
        if not value:
            return None, "invalid_customer_phone"
        lowered = value.lower()
        if lowered.startswith("test:"):
            return None, "synthetic_test_phone"
        if lowered.startswith("whatsapp:"):
            value = value.split(":", 1)[1].strip()
        compact = re.sub(r"[\s().-]", "", value)
        if not _PHONE_PATTERN.fullmatch(compact):
            return None, "invalid_customer_phone"
        return compact.lstrip("+"), None

    @staticmethod
    def _delivery_suffix(order: Order) -> str:
        parts: list[str] = []
        if order.delivery_provider:
            parts.append(f"via {order.delivery_provider}")
        if order.estimated_delivery_minutes is not None:
            parts.append(f"Estimated arrival: {order.estimated_delivery_minutes} minutes.")
        if parts:
            return " " + " ".join(parts)
        return ""

    @classmethod
    def build_status_message(cls, order: Order) -> str:
        template = _STATUS_MESSAGES[order.status]
        message = template.format(order_number=order.order_number)
        if order.status == "out_for_delivery":
            provider = f" via {order.delivery_provider}" if order.delivery_provider else ""
            eta = f" Estimated arrival: {order.estimated_delivery_minutes} minutes." if order.estimated_delivery_minutes is not None else ""
            return f"Your order {order.order_number} is out for delivery{provider}.{eta} Please keep your phone available because the rider may call."
        if order.status in {"confirmed", "preparing", "ready", "rider_assigned"}:
            return message + cls._delivery_suffix(order)
        return message

    @classmethod
    def build_delivery_message(cls, order: Order) -> str:
        provider = f" via {order.delivery_provider}" if order.delivery_provider else ""
        eta = f" Estimated arrival: {order.estimated_delivery_minutes} minutes." if order.estimated_delivery_minutes is not None else ""
        return f"Delivery update for your order {order.order_number}{provider}.{eta} Please keep your phone available because the rider may call."

    def _send(self, *, order: Order, message: str) -> NotificationResult:
        recipient_phone, reason = self.normalize_phone(order.customer_phone)
        if reason:
            result = NotificationResult(status="skipped", reason=reason)
            self._log_result(order, result, attempted=False)
            return result
        try:
            result = self.provider.send_text_message(recipient_phone=recipient_phone or "", text=message)
        except Exception:
            logger.exception("order_notification_transport_exception", extra={"event": "order_notification_transport_exception", "order_id": order.id, "order_number": order.order_number, "status": order.status})
            result = NotificationResult(status="failed", reason="provider_unavailable")
        self._log_result(order, result, attempted=result.status != "skipped")
        return result

    @staticmethod
    def _log_result(order: Order, result: NotificationResult, *, attempted: bool) -> None:
        logger.info("order_notification_result", extra={
            "event": "order_notification_result",
            "order_id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "notification_attempted": attempted,
            "notification_status": result.status,
            "message_sid": result.message_sid,
            "reason": result.reason,
        })

    def notify_status(self, order: Order) -> NotificationResult:
        if order.status not in _STATUS_MESSAGES:
            result = NotificationResult(status="skipped", reason="status_has_no_customer_message")
            self._log_result(order, result, attempted=False)
            return result
        return self._send(order=order, message=self.build_status_message(order))

    def notify_delivery_update(self, order: Order) -> NotificationResult:
        if order.status not in {"rider_assigned", "out_for_delivery"}:
            result = NotificationResult(status="skipped", reason="status_not_delivery_relevant")
            self._log_result(order, result, attempted=False)
            return result
        return self._send(order=order, message=self.build_delivery_message(order))




