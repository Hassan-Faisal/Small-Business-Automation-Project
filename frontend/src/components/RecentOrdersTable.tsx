import type { RecentOrder } from "../types/dashboard";
import { StatusBadge } from "./StatusBadge";

function formatMoney(value: string | number) {
  return new Intl.NumberFormat("en-PK", { style: "currency", currency: "PKR", currencyDisplay: "code", maximumFractionDigits: 2 }).format(Number(value));
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-PK", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function RecentOrdersTable({ orders }: { orders: RecentOrder[] }) {
  if (orders.length === 0) {
    return <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center"><p className="font-semibold text-ink">No orders have been received yet.</p><p className="mt-2 text-sm text-slate-500">New customer orders will appear here.</p></div>;
  }
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-4 font-semibold">Order</th><th className="px-5 py-4 font-semibold">Customer</th><th className="px-5 py-4 font-semibold">Status</th><th className="px-5 py-4 font-semibold">Total</th><th className="px-5 py-4 font-semibold">Created</th></tr></thead>
          <tbody className="divide-y divide-slate-100">{orders.map((order) => <tr key={order.id} className="hover:bg-slate-50"><td className="whitespace-nowrap px-5 py-4 font-semibold text-ink">{order.order_number}</td><td className="whitespace-nowrap px-5 py-4 text-slate-600">{order.customer_phone}</td><td className="px-5 py-4"><StatusBadge status={order.status} /></td><td className="whitespace-nowrap px-5 py-4 font-medium text-ink">{formatMoney(order.total_amount)}</td><td className="whitespace-nowrap px-5 py-4 text-slate-500">{formatDate(order.created_at)}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}