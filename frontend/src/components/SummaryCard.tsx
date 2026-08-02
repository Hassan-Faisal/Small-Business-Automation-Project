interface SummaryCardProps {
  label: string;
  value: string | number;
  detail?: string;
  accent?: "teal" | "amber" | "slate";
}

const accents = {
  teal: "border-teal-100 bg-teal-50",
  amber: "border-amber-100 bg-amber-50",
  slate: "border-slate-200 bg-white",
};

export function SummaryCard({ label, value, detail, accent = "slate" }: SummaryCardProps) {
  return (
    <article className={`rounded-2xl border p-5 shadow-sm ${accents[accent]}`}>
      <p className="text-sm font-medium text-slate-600">{label}</p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-ink">{value}</p>
      {detail && <p className="mt-2 text-xs text-slate-500">{detail}</p>}
    </article>
  );
}