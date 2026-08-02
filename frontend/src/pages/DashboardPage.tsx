import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SummaryCard } from "../components/SummaryCard";
import { RecentOrdersTable } from "../components/RecentOrdersTable";
import { useAuth, isUnauthorized } from "../contexts/AuthContext";
import type { DashboardSummary } from "../types/dashboard";
import { isDashboardSummary } from "../utils/validation";

function formatMoney(value: string | number) { return new Intl.NumberFormat("en-PK", { style: "currency", currency: "PKR", currencyDisplay: "code", maximumFractionDigits: 2 }).format(Number(value)); }

export function DashboardPage() {
  const { user, clearSession } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    api.get<DashboardSummary>("/admin/dashboard/summary")
      .then((response) => {
        if (!isDashboardSummary(response.data)) throw new Error("Unexpected dashboard response");
        if (mounted) { setSummary(response.data); setError(""); }
      })
      .catch((reason: unknown) => { if (!mounted) return; if (isUnauthorized(reason)) clearSession(); else setError("We could not load your dashboard right now. Please try again."); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [clearSession]);

  if (loading) return <div className="flex min-h-[60vh] items-center justify-center text-sm text-slate-500">Loading your dashboard…</div>;
  if (error) return <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700"><p className="font-semibold">Something went wrong</p><p className="mt-2">{error}</p></div>;
  if (!summary) return null;

  return <div><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-sm font-semibold uppercase tracking-widest text-teal-600">Good morning, {user?.full_name?.split(" ")[0]}</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-ink">Today at a glance</h1><p className="mt-2 text-sm text-slate-500">A simple view of your business activity.</p></div><div className="rounded-xl bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">Business overview</div></div><section aria-label="Summary" className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><SummaryCard label="Today’s orders" value={summary.today_orders} detail="All orders received today" accent="teal" /><SummaryCard label="Today’s revenue" value={formatMoney(summary.today_revenue)} detail="Delivered and completed orders" accent="amber" /><SummaryCard label="Pending orders" value={summary.pending_orders} detail="Waiting to be handled" /><SummaryCard label="Preparing orders" value={summary.preparing_orders} detail="Currently in the kitchen" /><SummaryCard label="Delivered orders" value={summary.delivered_orders} detail="Successfully delivered" /><SummaryCard label="Active subscriptions" value={summary.active_subscriptions} detail="Currently active plans" /><SummaryCard label="Total customers" value={summary.total_customers} detail="Known customer contacts" /></section><section className="mt-8 grid gap-6 lg:grid-cols-[0.8fr_1.2fr]"><article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><p className="text-sm font-semibold uppercase tracking-widest text-slate-500">Top selling item</p>{summary.top_selling_item ? <div className="mt-8"><p className="text-2xl font-bold text-ink">{summary.top_selling_item.name}</p><p className="mt-2 text-sm text-slate-500">{summary.top_selling_item.quantity} sold today</p></div> : <div className="mt-8 rounded-xl bg-slate-50 p-5 text-sm text-slate-500">No sales have been recorded yet today.</div>}</article><article><div className="mb-4 flex items-center justify-between"><div><p className="text-sm font-semibold uppercase tracking-widest text-slate-500">Recent orders</p><h2 className="mt-1 text-xl font-bold text-ink">Latest activity</h2></div><span className="text-xs text-slate-500">Last 5 orders</span></div><RecentOrdersTable orders={summary.recent_orders} /></article></section></div>;
}