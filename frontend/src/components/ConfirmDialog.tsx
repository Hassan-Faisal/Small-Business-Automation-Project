interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel: string;
  confirming: boolean;
  error: string;
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmDialog({ title, message, confirmLabel, confirming, error, onConfirm, onClose }: ConfirmDialogProps) {
  return <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/40 px-5 py-8" role="presentation"><div role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-soft"><h2 id="confirm-dialog-title" className="text-xl font-bold text-ink">{title}</h2><p className="mt-3 text-sm leading-6 text-slate-600">{message}</p>{error && <p role="alert" className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}<div className="mt-6 flex justify-end gap-3"><button type="button" disabled={confirming} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60" onClick={onClose}>Cancel</button><button type="button" disabled={confirming} className="rounded-xl bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60" onClick={onConfirm}>{confirming ? "Deleting…" : confirmLabel}</button></div></div></div>;
}
