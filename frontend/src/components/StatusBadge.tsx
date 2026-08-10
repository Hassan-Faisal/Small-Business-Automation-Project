const labels: Record<string, string> = {
  draft: "Draft",
  pending: "Pending",
  confirmed: "Confirmed",
  preparing: "Preparing",
  ready: "Ready",
  rider_assigned: "Rider assigned",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  completed: "Completed",
  cancelled: "Cancelled",
};

const colors: Record<string, string> = {
  draft: "bg-amber-100 text-amber-800",
  pending: "bg-amber-100 text-amber-800",
  confirmed: "bg-blue-100 text-blue-800",
  preparing: "bg-violet-100 text-violet-800",
  ready: "bg-teal-100 text-teal-800",
  rider_assigned: "bg-sky-100 text-sky-800",
  out_for_delivery: "bg-orange-100 text-orange-800",
  delivered: "bg-emerald-100 text-emerald-800",
  completed: "bg-slate-200 text-slate-800",
  cancelled: "bg-rose-100 text-rose-800",
};

export function StatusBadge({ status }: { status: string }) {
  const key = status.toLowerCase();
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${colors[key] || "bg-slate-100 text-slate-700"}`}>{labels[key] || status.replace(/_/g, " ")}</span>;
}