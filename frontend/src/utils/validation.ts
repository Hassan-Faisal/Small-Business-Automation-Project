import type { AdminProfile, AuthResponse } from "../types/admin";
import type { DashboardSummary, RecentOrder, TopSellingItem } from "../types/dashboard";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isMoney(value: unknown): value is string | number {
  return (typeof value === "string" || typeof value === "number") && Number.isFinite(Number(value));
}

export function isAdminProfile(value: unknown): value is AdminProfile {
  return (
    isRecord(value)
    && typeof value.id === "number"
    && typeof value.full_name === "string"
    && typeof value.email === "string"
    && typeof value.role === "string"
    && typeof value.is_active === "boolean"
    && typeof value.created_at === "string"
    && typeof value.updated_at === "string"
    && (value.last_login_at === null || typeof value.last_login_at === "string")
  );
}

export function isAuthResponse(value: unknown): value is AuthResponse {
  return isRecord(value) && typeof value.message === "string" && isAdminProfile(value.admin);
}

function isTopSellingItem(value: unknown): value is TopSellingItem {
  return isRecord(value) && typeof value.name === "string" && typeof value.quantity === "number";
}

function isRecentOrder(value: unknown): value is RecentOrder {
  return (
    isRecord(value)
    && typeof value.id === "number"
    && typeof value.order_number === "string"
    && typeof value.customer_phone === "string"
    && typeof value.status === "string"
    && isMoney(value.total_amount)
    && typeof value.created_at === "string"
    && !Number.isNaN(Date.parse(value.created_at))
  );
}

export function isDashboardSummary(value: unknown): value is DashboardSummary {
  if (!isRecord(value)) return false;

  const countFields = [
    "today_orders",
    "pending_orders",
    "draft_orders",
    "confirmed_orders",
    "preparing_orders",
    "ready_orders",
    "rider_assigned_orders",
    "out_for_delivery_orders",
    "delivered_orders",
    "completed_orders",
    "cancelled_orders",
    "active_subscriptions",
    "total_customers",
  ];

  return (
    countFields.every((field) => typeof value[field] === "number")
    && isMoney(value.today_revenue)
    && (value.top_selling_item === null || isTopSellingItem(value.top_selling_item))
    && Array.isArray(value.recent_orders)
    && value.recent_orders.every(isRecentOrder)
  );
}
