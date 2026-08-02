from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TopSellingItemResponse(BaseModel):
    name: str
    quantity: int


class RecentOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    customer_phone: str
    status: str
    total_amount: Decimal
    created_at: datetime


class AdminDashboardSummaryResponse(BaseModel):
    today_orders: int
    pending_orders: int
    draft_orders: int
    confirmed_orders: int
    preparing_orders: int
    ready_orders: int
    rider_assigned_orders: int
    out_for_delivery_orders: int
    delivered_orders: int
    completed_orders: int
    cancelled_orders: int
    today_revenue: Decimal
    active_subscriptions: int
    total_customers: int
    top_selling_item: TopSellingItemResponse | None
    recent_orders: list[RecentOrderResponse]