import { describe, expect, it } from "vitest";

import { isDashboardSummary } from "./validation";

const completeSummary = {
  period: "today",
  total_orders: 3,
  total_revenue: "320.00",
  period_orders: 2,
  period_revenue: "320.00",
  today_orders: 3,
  pending_orders: 0,
  draft_orders: 0,
  confirmed_orders: 2,
  preparing_orders: 0,
  ready_orders: 0,
  rider_assigned_orders: 0,
  out_for_delivery_orders: 0,
  delivered_orders: 0,
  completed_orders: 1,
  cancelled_orders: 1,
  today_revenue: "320.00",
  active_subscriptions: 0,
  total_customers: 3,
  top_selling_item: null,
  performance: [{ date: "2026-08-02", orders: 3, revenue: "320.00" }],
  recent_orders: [{
    id: 1,
    order_number: "TF-260809-6DE2",
    customer_phone: "redacted",
    status: "confirmed",
    total_amount: "185.00",
    created_at: "2026-08-01T20:00:00Z",
  }],
};

describe("dashboard response contract", () => {
  it("accepts complete production-style decimal serialization", () => {
    expect(isDashboardSummary(completeSummary)).toBe(true);
  });

  it("rejects a response missing core metrics instead of inventing zeros", () => {
    const incomplete = { ...completeSummary } as Record<string, unknown>;
    delete incomplete.total_orders;
    delete incomplete.total_revenue;
    delete incomplete.period_orders;
    delete incomplete.period_revenue;
    expect(isDashboardSummary(incomplete)).toBe(false);
  });
});
