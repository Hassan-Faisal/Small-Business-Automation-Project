import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { RecentOrdersTable } from "../components/RecentOrdersTable";
import { MetaEmbeddedSignup } from "../components/MetaEmbeddedSignup";
import { SummaryCard } from "../components/SummaryCard";
import { isUnauthorized, useAuth } from "../contexts/AuthContext";
import type { DashboardPeriod, DashboardSummary } from "../types/dashboard";
import { isDashboardSummary } from "../utils/validation";
import { useVisibilityRefresh } from "../hooks/useVisibilityRefresh";

const PERIODS: Array<{ value: DashboardPeriod; label: string }> = [
  { value: "today", label: "Today" },
  { value: "7d", label: "7 Days" },
  { value: "30d", label: "30 Days" },
  { value: "all", label: "All Time" },
];

function formatMoney(value: string | number) { return new Intl.NumberFormat("en-PK", { style: "currency", currency: "PKR", currencyDisplay: "code", maximumFractionDigits: 2 }).format(Number(value)); }
function greeting() { const hour = Number(new Date().toLocaleString("en-US", { timeZone: "Asia/Karachi", hour: "numeric", hour12: false })); return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"; }

export interface OperationalCounts {
  pending: number;
  preparing: number;
  ready: number;
  outForDelivery: number;
  completed: number;
}

export function getOperationalCounts(summary: DashboardSummary): OperationalCounts {
  return {
    pending: summary.pending_orders + summary.confirmed_orders,
    preparing: summary.preparing_orders,
    ready: summary.ready_orders + summary.rider_assigned_orders,
    outForDelivery: summary.out_for_delivery_orders,
    completed: summary.delivered_orders + summary.completed_orders,
  };
}

function periodLabel(period: DashboardPeriod): string { return PERIODS.find((item) => item.value === period)?.label || "Today"; }
function periodHeading(period: DashboardPeriod): string { return period === "today" ? "Today’s performance" : period === "all" ? "All-time performance" : `Last ${period === "7d" ? "7" : "30"} days`; }

export function DashboardPage() {
  const { user, clearSession } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [period, setPeriod] = useState<DashboardPeriod>("today");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshSummary = useCallback(async (background: boolean) => {
    if (!background) {
      setLoading(true);
      setError("");
    }
    try {
      const response = await api.get<DashboardSummary>("/admin/dashboard/summary", { params: { period } });
      if (!isDashboardSummary(response.data)) throw new Error("Unexpected dashboard response");
      setSummary(response.data);
      setError("");
    } catch (reason: unknown) {
      if (isUnauthorized(reason)) clearSession();
      else if (!background) setError("We could not load your dashboard right now. Please try again.");
    } finally {
      if (!background) setLoading(false);
    }
  }, [clearSession, period]);

  useEffect(() => {
    void refreshSummary(false);
  }, [refreshSummary]);

  useVisibilityRefresh(() => refreshSummary(true));


  if (loading) return <div className="flex min-h-[60vh] items-center justify-center text-sm text-slate-500">Loading your dashboard…</div>;
  if (error) return <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700"><p className="font-semibold">Something went wrong</p><p className="mt-2">{error}</p></div>;
  if (!summary) return null;

  const operations = getOperationalCounts(summary);

  return <div>
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-sm font-semibold uppercase tracking-widest text-teal-600">{greeting()}, {user?.full_name?.split(" ")[0]}</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-ink">Today at a glance</h1><p className="mt-2 text-sm text-slate-500">Run today’s orders and keep your kitchen moving.</p></div><div className="rounded-xl bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">Asia/Karachi business time</div></div>

    <section aria-labelledby="overview-heading" className="mt-8"><h2 id="overview-heading" className="text-lg font-bold text-ink">Business overview</h2><div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><SummaryCard label="Total orders" value={summary.total_orders} detail="All customer orders" accent="teal" /><SummaryCard label="Total revenue" value={formatMoney(summary.total_revenue)} detail="Revenue from fulfilled orders" accent="amber" /><SummaryCard label="Today’s orders" value={summary.today_orders} detail="Orders received today" /><SummaryCard label="Today’s revenue" value={formatMoney(summary.today_revenue)} detail="Revenue earned today" /></div></section>

    <section aria-labelledby="operations-heading" className="mt-8"><h2 id="operations-heading" className="text-lg font-bold text-ink">Order operations</h2><div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"><SummaryCard label="Pending" value={operations.pending} detail="New and confirmed" /><SummaryCard label="Preparing" value={operations.preparing} detail="In the kitchen" /><SummaryCard label="Ready" value={operations.ready} detail="Ready for pickup" /><SummaryCard label="Out for delivery" value={operations.outForDelivery} detail="On the way" /><SummaryCard label="Completed" value={operations.completed} detail="Delivered and closed" /></div></section>

    <section aria-labelledby="performance-heading" className="mt-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 id="performance-heading" className="text-lg font-bold text-ink">Business performance</h2><p className="mt-1 text-sm text-slate-500">{periodHeading(period)}</p><p className="mt-1 text-sm text-slate-600">{summary.period_orders} {summary.period_orders === 1 ? "order" : "orders"} · {formatMoney(summary.period_revenue)} revenue</p></div><div className="flex max-w-full flex-wrap rounded-xl border border-slate-200 bg-white p-1 shadow-sm" aria-label="Performance period">{PERIODS.map((item) => <button key={item.value} type="button" onClick={() => setPeriod(item.value)} className={`rounded-lg px-3 py-2 text-xs font-semibold transition ${period === item.value ? "bg-ink text-white" : "text-slate-600 hover:bg-slate-100"}`}>{item.label}</button>)}</div></div><div className="mt-4 grid gap-6 lg:grid-cols-[1.5fr_0.8fr]"><PerformanceChart points={summary.performance} period={period} /><article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><p className="text-sm font-semibold uppercase tracking-widest text-slate-500">Top selling item</p>{summary.top_selling_item ? <div className="mt-8"><p className="text-2xl font-bold text-ink">{summary.top_selling_item.name}</p><p className="mt-2 text-sm text-slate-500">{summary.top_selling_item.quantity} sold</p><p className="mt-5 text-lg font-semibold text-teal-700">{formatMoney(summary.top_selling_item.revenue)} revenue</p></div> : <div className="mt-8 rounded-xl bg-slate-50 p-5 text-sm text-slate-500">No sales recorded for {periodLabel(period).toLowerCase()}.</div>}</article></div></section>

    <section aria-labelledby="quick-actions-heading" className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div><h2 id="quick-actions-heading" className="text-base font-bold text-ink">Quick actions</h2><p className="mt-1 text-sm text-slate-500">Keep daily operations close at hand.</p></div><div className="flex flex-wrap gap-2"><Link to="/orders" className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-ink hover:bg-slate-50">View orders</Link><Link to="/menu" className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-ink hover:bg-slate-50">Manage menu</Link><Link to="/menu" className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700">Add menu item</Link></div></div></section>

    <MetaEmbeddedSignup />

    <section aria-labelledby="recent-orders-heading" className="mt-8"><div className="mb-4"><h2 id="recent-orders-heading" className="text-lg font-bold text-ink">Recent orders</h2><p className="mt-1 text-sm text-slate-500">Your latest customer orders</p></div><RecentOrdersTable orders={summary.recent_orders} /></section>
  </div>;
}

function formatPointLabel(value: string, period: DashboardPeriod): string {
  if (period === "today") return "Today";
  if (value.length === 7) return new Intl.DateTimeFormat("en-PK", { month: "short", timeZone: "UTC" }).format(new Date(`${value}-01T00:00:00Z`));
  return value.slice(5);
}

function PerformanceChart({ points, period }: { points: DashboardSummary["performance"]; period: DashboardPeriod }) {
  const maxOrders = Math.max(...points.map((point) => point.orders), 1);
  const hasActivity = points.some((point) => point.orders > 0 || Number(point.revenue) > 0);
  if (!hasActivity) return <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">No order activity for {periodLabel(period).toLowerCase()} yet.</div>;
  return <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><div className="flex items-center justify-between"><div><p className="text-sm font-semibold uppercase tracking-widest text-slate-500">Orders & revenue</p><p className="mt-1 text-xs text-slate-400">{periodHeading(period)}</p></div><span className="text-xs text-slate-400">Bars show orders</span></div><div className="mt-8 overflow-x-auto"><div className={`flex h-44 items-end gap-2 sm:gap-4 ${points.length > 12 ? "min-w-[720px]" : "min-w-full"}`}>{points.map((point) => <div key={point.date} className="flex min-w-0 flex-1 flex-col items-center justify-end gap-2"><span className="text-[10px] font-semibold text-slate-500">{point.orders}</span><div className="w-full rounded-t-lg bg-teal-600" style={{ height: `${Math.max((point.orders / maxOrders) * 100, point.orders ? 8 : 2)}%` }} title={`${point.orders} orders · ${formatMoney(point.revenue)}`} /><span className="text-[10px] text-slate-400">{formatPointLabel(point.date, period)}</span><span className="max-w-full truncate text-[10px] text-slate-500">{formatMoney(point.revenue)}</span></div>)}</div></div></article>;
}
