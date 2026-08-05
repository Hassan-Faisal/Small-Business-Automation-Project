export type ToastKind = "success" | "error";

export interface ToastData {
  id: number;
  kind: ToastKind;
  message: string;
}

export function Toast({ toast, onClose }: { toast: ToastData; onClose: () => void }) {
  const styles = toast.kind === "success" ? "border-teal-200 bg-teal-50 text-teal-700" : "border-rose-200 bg-rose-50 text-rose-700";
  return <div role={toast.kind === "error" ? "alert" : "status"} className={`fixed bottom-5 right-5 z-50 flex max-w-sm items-start gap-4 rounded-xl border px-4 py-3 text-sm shadow-lg ${styles}`}><p className="leading-5">{toast.message}</p><button type="button" aria-label="Dismiss notification" className="font-bold opacity-70 hover:opacity-100" onClick={onClose}>×</button></div>;
}
