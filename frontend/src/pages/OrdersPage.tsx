import { useCallback, useEffect, useMemo, useState } from "react";

import { getOrder, listOrders, updateOrderDelivery, updateOrderStatus } from "../api/orders";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { OrderDetailsDrawer } from "../components/OrderDetailsDrawer";
import { StatusBadge } from "../components/StatusBadge";
import { Toast, type ToastData, type ToastKind } from "../components/Toast";
import { isUnauthorized, useAuth } from "../contexts/AuthContext";
import type { OrderDeliveryUpdatePayload, OrderDetail, OrderFilters, OrderListItem, OrderStatus } from "../types/order";
import { getApiErrorMessage } from "../utils/errors";
import { formatMoney, formatOrderDate } from "../utils/orderFormatting";
import { useVisibilityRefresh } from "../hooks/useVisibilityRefresh";

const EMPTY_FILTERS: OrderFilters = {
  status: "", date_from: "", date_to: "", customer_phone: "", order_number: "", search: "",
};

const ACTIONS: Record<string, Array<{ status: OrderStatus; label: string; requiresConfirmation: boolean }>> = {
  draft: [{ status: "confirmed", label: "Confirm", requiresConfirmation: false }, { status: "cancelled", label: "Cancel order", requiresConfirmation: true }],
  confirmed: [{ status: "preparing", label: "Start Preparing", requiresConfirmation: false }, { status: "cancelled", label: "Cancel order", requiresConfirmation: true }],
  preparing: [{ status: "ready", label: "Mark Ready", requiresConfirmation: false }, { status: "cancelled", label: "Cancel order", requiresConfirmation: true }],
  ready: [{ status: "rider_assigned", label: "Assign Rider", requiresConfirmation: false }],
  rider_assigned: [{ status: "out_for_delivery", label: "Out for Delivery", requiresConfirmation: false }],
  out_for_delivery: [{ status: "completed", label: "Mark Completed", requiresConfirmation: true }],
  delivered: [{ status: "completed", label: "Mark Completed", requiresConfirmation: true }],
};

export function getOrderActions(status: string) {
  return ACTIONS[status.toLowerCase()] || [];
}

export function OrdersPage() {
  const { clearSession } = useAuth();
  const [filters, setFilters] = useState<OrderFilters>(EMPTY_FILTERS);
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<OrderDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [action, setAction] = useState<{ status: OrderStatus; label: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<ToastData | null>(null);

  const refreshOrders = useCallback(async (background: boolean) => {
    if (!background) {
      setLoading(true);
      setLoadError("");
    }
    try {
      const response = await listOrders(filters, page);
      setOrders(response.items);
      setPages(response.pages);
      setTotal(response.total);
      setLoadError("");
    } catch (reason: unknown) {
      if (isUnauthorized(reason)) clearSession();
      else if (!background) setLoadError(getApiErrorMessage(reason, "We could not load orders right now. Please try again."));
    } finally {
      if (!background) setLoading(false);
    }
  }, [clearSession, filters, page]);

  useEffect(() => {
    void refreshOrders(false);
  }, [refreshOrders]);

  useVisibilityRefresh(() => refreshOrders(true));

  useEffect(() => {
    if (!toast) return undefined;
    const timeout = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  async function openOrder(id: number) {
    setSelectedId(id);
    setDetail(null);
    setDetailError("");
    setDetailLoading(true);
    try {
      const response = await getOrder(id);
      setDetail(response);
    } catch (reason: unknown) {
      if (isUnauthorized(reason)) clearSession();
      else setDetailError(getApiErrorMessage(reason, "We could not load this order."));
    } finally {
      setDetailLoading(false);
    }
  }

  function showToast(message: string, kind: ToastKind = "success") {
    setToast({ id: Date.now(), kind, message });
  }

  function changeFilter(key: keyof OrderFilters, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  function resetFilters() {
    setFilters(EMPTY_FILTERS);
    setPage(1);
  }

  function updateListFromDetail(updated: OrderDetail) {
    setOrders((current) => current.map((item) => item.id === updated.id ? {
      ...item,
      status: updated.status,
      total_amount: updated.total_amount,
      updated_at: updated.updated_at,
      item_count: updated.items.length,
      delivery_provider: updated.delivery_provider,
    } : item));
  }

  async function saveStatus(nextAction = action) {
    if (!detail || !nextAction) return;
    setSaving(true);
    try {
      const updated = await updateOrderStatus(detail.id, { status: nextAction.status });
      setDetail(updated);
      updateListFromDetail(updated);
      setAction(null);
      showToast(`${nextAction.label} completed.`);
    } catch (reason: unknown) {
      if (isUnauthorized(reason)) clearSession();
      else showToast(getApiErrorMessage(reason, "We could not update this order. The previous state was kept."), "error");
    } finally {
      setSaving(false);
    }
  }

  async function saveDelivery(payload: OrderDeliveryUpdatePayload) {
    if (!detail) return;
    setSaving(true);
    try {
      const updated = await updateOrderDelivery(detail.id, payload);
      setDetail(updated);
      updateListFromDetail(updated);
      showToast("Delivery details updated.");
    } catch (reason: unknown) {
      if (isUnauthorized(reason)) clearSession();
      else showToast(getApiErrorMessage(reason, "We could not update delivery details."), "error");
      throw reason;
    } finally {
      setSaving(false);
    }
  }

  const selectedActions = useMemo(() => detail ? getOrderActions(detail.status) : [], [detail]);

  return <div>
    <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
      <div><p className="text-sm font-semibold uppercase tracking-widest text-teal-600">Operations</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-ink">Orders</h1><p className="mt-2 text-sm text-slate-500">Manage customer orders and delivery progress.</p></div>
      <div className="rounded-xl bg-white px-4 py-3 text-sm text-slate-600 shadow-sm"><span className="font-semibold text-ink">{total}</span> total record{total === 1 ? "" : "s"}</div>
    </div>
    <section aria-label="Order filters" className="mt-8 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <FilterInput id="order-search" label="Search" value={filters.search} placeholder="Search by order number or phone" onChange={(value) => changeFilter("search", value)} />
        <FilterSelect id="order-status" label="Status" value={filters.status} onChange={(value) => changeFilter("status", value)} options={[["", "All statuses"], ["draft", "Draft"], ["confirmed", "Confirmed"], ["preparing", "Preparing"], ["ready", "Ready"], ["rider_assigned", "Rider assigned"], ["out_for_delivery", "Out for delivery"], ["delivered", "Delivered"], ["completed", "Completed"], ["cancelled", "Cancelled"]]} />
        <FilterInput id="date-from" label="Date from" type="date" value={filters.date_from} onChange={(value) => changeFilter("date_from", value)} />
        <FilterInput id="date-to" label="Date to" type="date" value={filters.date_to} onChange={(value) => changeFilter("date_to", value)} />
      </div>
      <button type="button" className="mt-4 rounded-lg px-3 py-2 text-sm font-semibold text-teal-700 hover:bg-teal-50 focus:outline-none focus:ring-4 focus:ring-teal-100" onClick={resetFilters}>Reset filters</button>
    </section>
    <QuickStatusFilters value={filters.status} onChange={(value) => changeFilter("status", value)} />
    <section className="mt-8">
      {loading ? <LoadingOrders /> : loadError ? <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700"><p className="font-semibold">Something went wrong</p><p className="mt-2">{loadError}</p><button type="button" className="mt-4 rounded-lg bg-rose-600 px-4 py-2 font-semibold text-white hover:bg-rose-700" onClick={() => { setLoadError(""); setPage((current) => current); window.location.reload(); }}>Try again</button></div> : orders.length === 0 ? <EmptyOrders filtered={Object.values(filters).some(Boolean)} onReset={resetFilters} /> : <OrdersTable orders={orders} onOpen={openOrder} />}
    </section>
    {!loading && !loadError && total > 0 && <nav aria-label="Orders pagination" className="mt-6 flex flex-col gap-3 text-sm text-slate-600 sm:flex-row sm:items-center sm:justify-between"><span>Page {page} of {Math.max(pages, 1)}</span><div className="flex gap-2"><button type="button" disabled={page <= 1 || loading} className="rounded-lg border border-slate-300 px-4 py-2 font-semibold hover:bg-white disabled:cursor-not-allowed disabled:opacity-40" onClick={() => setPage((current) => current - 1)}>Previous</button><button type="button" disabled={page >= pages || loading} className="rounded-lg border border-slate-300 px-4 py-2 font-semibold hover:bg-white disabled:cursor-not-allowed disabled:opacity-40" onClick={() => setPage((current) => current + 1)}>Next</button></div></nav>}
    {selectedId !== null && <OrderDetailsDrawer order={detail} loading={detailLoading} error={detailError} savingDelivery={saving} nextActions={selectedActions} onClose={() => { if (!saving) { setSelectedId(null); setDetail(null); } }} onStatusAction={(status) => { const selected = selectedActions.find((item) => item.status === status); if (!selected) return; if (selected.requiresConfirmation) setAction({ status, label: selected.label }); else void saveStatus({ status, label: selected.label }); }} onSaveDelivery={saveDelivery} />}
    {action && <ConfirmDialog title={action.status === "cancelled" ? `Cancel order ${detail?.order_number || ""}?` : `Mark ${detail?.order_number || ""} completed?`} message={action.status === "cancelled" ? "This order will be cancelled and cannot be reopened." : "This confirms delivery is finished."} confirmLabel={action.label} confirming={saving} error="" onConfirm={() => void saveStatus()} onClose={() => { if (!saving) setAction(null); }} />}
    {toast && <Toast toast={toast} onClose={() => setToast(null)} />}
  </div>;
}

function FilterInput({ id, label, value, placeholder, type = "text", onChange }: { id: string; label: string; value: string; placeholder?: string; type?: string; onChange: (value: string) => void }) {
  return <div><label htmlFor={id} className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</label><input id={id} type={type} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100" /></div>;
}

function FilterSelect({ id, label, value, options, onChange }: { id: string; label: string; value: string; options: Array<[string, string]>; onChange: (value: string) => void }) {
  return <div><label htmlFor={id} className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</label><select id={id} value={value} onChange={(event) => onChange(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100">{options.map(([option, label]) => <option key={option} value={option}>{label}</option>)}</select></div>;
}

function QuickStatusFilters({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const filters: Array<[string, string]> = [["", "All"], ["confirmed", "Confirmed"], ["preparing", "Preparing"], ["ready", "Ready"], ["out_for_delivery", "Out for Delivery"], ["completed", "Completed"], ["cancelled", "Cancelled"]];
  return <div className="mt-5 flex flex-wrap gap-2" aria-label="Quick status filters">{filters.map(([status, label]) => <button key={status || "all"} type="button" aria-pressed={value === status} className={value === status ? "rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white" : "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:border-teal-300 hover:text-teal-700"} onClick={() => onChange(status)}>{label}</button>)}</div>
}

function OrdersTable({ orders, onOpen }: { orders: OrderListItem[]; onOpen: (id: number) => void }) {
  return <>
    <div className="hidden overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm md:block">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-4">Order #</th><th className="px-5 py-4">Customer</th><th className="px-5 py-4">Items</th><th className="px-5 py-4">Total</th><th className="px-5 py-4">Status</th><th className="px-5 py-4">Created</th><th className="px-5 py-4">Action</th></tr></thead>
        <tbody className="divide-y divide-slate-100">{orders.map((order) => <tr key={order.id} className="hover:bg-slate-50"><td className="px-5 py-4"><button type="button" className="font-semibold text-teal-700 underline-offset-2 hover:underline focus:outline-none focus:ring-4 focus:ring-teal-100" onClick={() => onOpen(order.id)}>{order.order_number}</button></td><td className="px-5 py-4 text-slate-600">{order.customer_phone}</td><td className="px-5 py-4 text-slate-600">{order.item_count === 1 ? "1 item" : `${order.item_count} items`}</td><td className="whitespace-nowrap px-5 py-4 font-medium text-ink">{formatMoney(order.total_amount)}</td><td className="px-5 py-4"><StatusBadge status={order.status} /></td><td className="whitespace-nowrap px-5 py-4 text-slate-500">{formatOrderDate(order.created_at)}</td><td className="px-5 py-4"><button type="button" className="font-semibold text-teal-700 hover:underline" onClick={() => onOpen(order.id)}>View Details</button></td></tr>)}</tbody>
      </table>
    </div>
    <div className="grid gap-4 md:hidden">{orders.map((order) => <button key={order.id} type="button" className="rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-sm focus:outline-none focus:ring-4 focus:ring-teal-100" onClick={() => onOpen(order.id)}><div className="flex items-start justify-between gap-3"><span className="font-bold text-teal-700">{order.order_number}</span><StatusBadge status={order.status} /></div><p className="mt-3 text-sm text-slate-600">{order.customer_phone}</p><div className="mt-4 grid grid-cols-2 gap-3 text-sm"><span><strong className="block text-xs uppercase tracking-wide text-slate-400">Total</strong>{formatMoney(order.total_amount)}</span><span><strong className="block text-xs uppercase tracking-wide text-slate-400">Created</strong>{formatOrderDate(order.created_at)}</span><span><strong className="block text-xs uppercase tracking-wide text-slate-400">Items</strong>{order.item_count}</span><span className="font-semibold text-teal-700">View Details</span></div></button>)}</div>
  </>;
}
function LoadingOrders() {
  return <div aria-label="Loading orders" className="space-y-3">{Array.from({ length: 5 }, (_, index) => <div key={index} className="h-20 animate-pulse rounded-2xl bg-white" />)}</div>;
}

function EmptyOrders({ filtered, onReset }: { filtered: boolean; onReset: () => void }) {
  return <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center shadow-sm"><h2 className="text-xl font-bold text-ink">{filtered ? "No orders match your current filters." : "No orders yet"}</h2><p className="mt-2 text-sm text-slate-500">{filtered ? "Try different filters or reset the current search." : "Orders will appear here when customers place them through WhatsApp."}</p>{filtered && <button type="button" className="mt-5 rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white hover:bg-teal-700" onClick={onReset}>Reset filters</button>}</div>;
}
