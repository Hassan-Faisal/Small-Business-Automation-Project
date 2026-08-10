import { useEffect, useRef, useState } from "react";

import { DELIVERY_PROVIDERS, type OrderDeliveryUpdatePayload, type OrderDetail, type OrderStatus } from "../types/order";
import { formatMoney } from "../utils/orderFormatting";
import { StatusBadge } from "./StatusBadge";

interface OrderDetailsDrawerProps {
  order: OrderDetail | null;
  loading: boolean;
  error: string;
  savingDelivery: boolean;
  onClose: () => void;
  onStatusAction: (status: OrderStatus) => void;
  onSaveDelivery: (payload: OrderDeliveryUpdatePayload) => Promise<void>;
  nextActions: Array<{ status: OrderStatus; label: string; requiresConfirmation: boolean }>;
}

export function OrderDetailsDrawer({
  order, loading, error, savingDelivery, onClose, onStatusAction, onSaveDelivery, nextActions,
}: OrderDetailsDrawerProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [provider, setProvider] = useState("");
  const [minutes, setMinutes] = useState("");
  const [riderNote, setRiderNote] = useState("");
  const [internalNote, setInternalNote] = useState("");
  const [deliveryError, setDeliveryError] = useState("");

  useEffect(() => {
    closeButtonRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!order) return;
    setProvider(order.delivery_provider || "");
    setMinutes(order.estimated_delivery_minutes?.toString() || "");
    setRiderNote(order.rider_note || "");
    setInternalNote(order.internal_note || "");
    setDeliveryError("");
  }, [order]);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  async function handleSaveDelivery(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedMinutes = minutes.trim() ? Number(minutes) : undefined;
    if (parsedMinutes !== undefined && (!Number.isInteger(parsedMinutes) || parsedMinutes <= 0)) {
      setDeliveryError("Estimated delivery minutes must be a positive whole number.");
      return;
    }
    setDeliveryError("");
    const payload: OrderDeliveryUpdatePayload = {};
    if (parsedMinutes !== undefined) payload.estimated_delivery_minutes = parsedMinutes;
    if (provider) payload.delivery_provider = provider as OrderDeliveryUpdatePayload["delivery_provider"];
    if (riderNote.trim()) payload.rider_note = riderNote.trim();
    if (internalNote.trim()) payload.internal_note = internalNote.trim();
    if (Object.keys(payload).length === 0) {
      setDeliveryError("Add at least one delivery detail before saving.");
      return;
    }
    try {
      await onSaveDelivery(payload);
    } catch {
      // The parent owns the user-facing API error toast.
    }
  }

  return <div className="fixed inset-0 z-30" role="presentation">
    <button type="button" aria-label="Close order details" className="absolute inset-0 h-full w-full cursor-default bg-ink/40" onClick={onClose} />
    <aside role="dialog" aria-modal="true" aria-labelledby="order-detail-title" className="absolute right-0 top-0 h-full w-full max-w-2xl overflow-y-auto bg-white p-5 shadow-2xl sm:p-8">
      <div className="flex items-start justify-between gap-4">
        <div><p className="text-sm font-semibold uppercase tracking-widest text-teal-600">Order details</p><h2 id="order-detail-title" className="mt-2 text-2xl font-bold text-ink">{order?.order_number || "Loading order"}</h2></div>
        <button ref={closeButtonRef} type="button" aria-label="Close order details" className="rounded-lg px-3 py-2 text-2xl leading-none text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-4 focus:ring-teal-100" onClick={onClose}>×</button>
      </div>
      {loading && <div className="mt-10 text-sm text-slate-500">Loading order details...</div>}
      {!loading && error && <div role="alert" className="mt-8 rounded-xl bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}
      {!loading && !error && order && <div className="mt-7 space-y-7">
        <section className="rounded-2xl bg-slate-50 p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm text-slate-500">Customer</p><p className="mt-1 font-semibold text-ink">{order.customer_phone}</p></div><StatusBadge status={order.status} /></div><dl className="mt-5 grid gap-4 sm:grid-cols-2"><Info label="Total amount" value={formatMoney(order.total_amount)} /><Info label="Delivery address" value={order.delivery_address} /><Info label="Customer instructions" value={order.customer_notes || "None provided"} /><Info label="Created" value={formatDate(order.created_at)} /><Info label="Updated" value={formatDate(order.updated_at)} /><Info label="Confirmed" value={formatDate(order.confirmed_at)} /><Info label="Completed" value={formatDate(order.completed_at)} /><Info label="Cancelled" value={formatDate(order.cancelled_at)} /></dl></section>
        {nextActions.length > 0 ? <section><h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Next actions</h3><div className="mt-3 flex flex-wrap gap-2">{nextActions.map((action) => <button key={action.status} type="button" disabled={savingDelivery} className={action.status === "cancelled" ? "rounded-xl border border-rose-200 px-4 py-2.5 text-sm font-semibold text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60" : "rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60"} onClick={() => onStatusAction(action.status)}>{action.label}</button>)}</div></section> : <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">No further actions</p>}
        <section><div className="flex items-center justify-between"><h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Items</h3><span className="text-sm text-slate-500">{order.items.length} item{order.items.length === 1 ? "" : "s"}</span></div><div className="mt-3 overflow-hidden rounded-xl border border-slate-200"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Item</th><th className="px-4 py-3">Qty</th><th className="px-4 py-3">Unit price</th><th className="px-4 py-3">Subtotal</th></tr></thead><tbody className="divide-y divide-slate-100">{order.items.map((item, index) => <tr key={`${item.product_name}-${index}`}><td className="px-4 py-3 font-medium text-ink">{item.product_name}</td><td className="px-4 py-3">{item.quantity}</td><td className="px-4 py-3">{formatMoney(item.unit_price)}</td><td className="px-4 py-3 font-semibold">{formatMoney(item.subtotal)}</td></tr>)}</tbody></table></div></section>
        <section><h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Delivery details</h3><form className="mt-3 space-y-4 rounded-2xl border border-slate-200 p-5" onSubmit={(event) => void handleSaveDelivery(event)}><div><label htmlFor="delivery-provider" className="mb-2 block text-sm font-semibold text-ink">Delivery provider</label><select id="delivery-provider" value={provider} onChange={(event) => setProvider(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm focus:border-teal-600 focus:outline-none focus:ring-4 focus:ring-teal-100"><option value="">Choose provider</option>{DELIVERY_PROVIDERS.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></div><div><label htmlFor="estimated-delivery-minutes" className="mb-2 block text-sm font-semibold text-ink">Estimated delivery minutes</label><input id="estimated-delivery-minutes" type="number" min="1" step="1" value={minutes} onChange={(event) => setMinutes(event.target.value)} className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm focus:border-teal-600 focus:outline-none focus:ring-4 focus:ring-teal-100" /></div><div><label htmlFor="rider-note" className="mb-2 block text-sm font-semibold text-ink">Rider note</label><textarea id="rider-note" rows={2} value={riderNote} onChange={(event) => setRiderNote(event.target.value)} className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm focus:border-teal-600 focus:outline-none focus:ring-4 focus:ring-teal-100" /></div><div><label htmlFor="internal-note" className="mb-2 block text-sm font-semibold text-ink">Internal note</label><textarea id="internal-note" rows={2} value={internalNote} onChange={(event) => setInternalNote(event.target.value)} className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm focus:border-teal-600 focus:outline-none focus:ring-4 focus:ring-teal-100" /> </div>{deliveryError && <p role="alert" className="text-sm text-rose-600">{deliveryError}</p>}<button type="submit" disabled={savingDelivery} className="w-full rounded-xl bg-ink px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60">{savingDelivery ? "Saving..." : "Save delivery details"}</button></form></section>
      </div>}
    </aside>
  </div>;
}

function Info({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</dt><dd className="mt-1 break-words text-sm text-slate-700">{value}</dd></div>;
}

function formatDate(value: string | null): string {
  return value ? new Intl.DateTimeFormat("en-PK", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Karachi" }).format(new Date(value)) : "Not recorded";
}