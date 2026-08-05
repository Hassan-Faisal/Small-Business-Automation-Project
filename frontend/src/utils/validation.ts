import type { AdminProfile, AuthResponse } from "../types/admin";
import type { DashboardSummary, RecentOrder, TopSellingItem } from "../types/dashboard";
import type { MenuItem, MenuItemListResponse } from "../types/menu";
import type { OrderDetail, OrderItemDetail, OrderListItem, OrderListResponse } from "../types/order";

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

export function isMenuItem(value: unknown): value is MenuItem {
  return (
    isRecord(value)
    && typeof value.id === "number"
    && typeof value.name === "string"
    && (value.description === null || typeof value.description === "string")
    && isMoney(value.price)
    && (value.meal_type === "breakfast" || value.meal_type === "lunch" || value.meal_type === "dinner")
    && typeof value.day_of_week === "string"
    && typeof value.availability === "boolean"
    && typeof value.is_active === "boolean"
  );
}

export function isMenuItemListResponse(value: unknown): value is MenuItemListResponse {
  return (
    isRecord(value)
    && Array.isArray(value.items)
    && value.items.every(isMenuItem)
    && typeof value.total === "number"
    && typeof value.page === "number"
    && typeof value.page_size === "number"
  );
}

export function isMenuItemDeactivationResponse(value: unknown): value is Pick<MenuItem, "id" | "availability" | "is_active"> & { message: string } {
  return (
    isRecord(value)
    && typeof value.id === "number"
    && typeof value.message === "string"
    && typeof value.availability === "boolean"
    && typeof value.is_active === "boolean"
  );
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

export function isOrderListItem(value: unknown): value is OrderListItem {
  return isRecord(value)
    && typeof value.id === "number"
    && typeof value.order_number === "string"
    && typeof value.customer_phone === "string"
    && typeof value.status === "string"
    && isMoney(value.total_amount)
    && isTimestamp(value.created_at)
    && isTimestamp(value.updated_at)
    && typeof value.item_count === "number"
    && (value.delivery_provider === null || typeof value.delivery_provider === "string");
}

export function isOrderListResponse(value: unknown): value is OrderListResponse {
  return isRecord(value)
    && Array.isArray(value.items)
    && value.items.every(isOrderListItem)
    && typeof value.page === "number"
    && typeof value.page_size === "number"
    && typeof value.total === "number"
    && typeof value.pages === "number";
}

export function isOrderItemDetail(value: unknown): value is OrderItemDetail {
  return isRecord(value)
    && typeof value.product_name === "string"
    && typeof value.quantity === "number"
    && isMoney(value.unit_price)
    && isMoney(value.subtotal);
}

export function isOrderDetail(value: unknown): value is OrderDetail {
  return isRecord(value)
    && typeof value.id === "number"
    && typeof value.order_number === "string"
    && typeof value.customer_phone === "string"
    && typeof value.status === "string"
    && isMoney(value.total_amount)
    && typeof value.delivery_address === "string"
    && isNullableString(value.customer_notes)
    && isNullableString(value.internal_note)
    && isTimestamp(value.created_at)
    && isTimestamp(value.updated_at)
    && (value.confirmed_at === null || isTimestamp(value.confirmed_at))
    && (value.completed_at === null || isTimestamp(value.completed_at))
    && (value.cancelled_at === null || isTimestamp(value.cancelled_at))
    && (value.estimated_delivery_minutes === null || typeof value.estimated_delivery_minutes === "number")
    && (value.delivery_provider === null || typeof value.delivery_provider === "string")
    && (value.rider_note === null || typeof value.rider_note === "string")
    && Array.isArray(value.items)
    && value.items.every(isOrderItemDetail);
}

