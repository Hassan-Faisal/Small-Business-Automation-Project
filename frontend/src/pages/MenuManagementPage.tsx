import { useEffect, useMemo, useState } from "react";

import { createMenuItem, deactivateMenuItem, listMenuItems, updateMenuItem, updateMenuItemAvailability } from "../api/menu";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { MenuItemCard } from "../components/MenuItemCard";
import { MenuItemModal } from "../components/MenuItemModal";
import { Toast, type ToastData, type ToastKind } from "../components/Toast";
import { isUnauthorized, useAuth } from "../contexts/AuthContext";
import type { CreateMenuItemPayload, MenuItem, UpdateMenuItemPayload } from "../types/menu";
import { getApiErrorMessage } from "../utils/errors";

type AvailabilityFilter = "all" | "available" | "sold_out";
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function LoadingCards() {
  return <div aria-label="Loading menu items" className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, index) => <div key={index} className="h-64 animate-pulse rounded-2xl border border-slate-200 bg-white p-5"><div className="h-5 w-2/3 rounded bg-slate-100" /><div className="mt-3 h-4 w-full rounded bg-slate-100" /><div className="mt-8 h-20 rounded bg-slate-100" /><div className="mt-6 h-9 rounded bg-slate-100" /></div>)}</div>;
}

export function MenuManagementPage() {
  const { clearSession } = useAuth();
  const [items, setItems] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [search, setSearch] = useState("");
  const [dayFilter, setDayFilter] = useState("all");
  const [mealTypeFilter, setMealTypeFilter] = useState("all");
  const [availabilityFilter, setAvailabilityFilter] = useState<AvailabilityFilter>("all");
  const [modal, setModal] = useState<{ mode: "create" | "edit"; item?: MenuItem } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [busyIds, setBusyIds] = useState<Set<number>>(() => new Set());
  const [deleteItem, setDeleteItem] = useState<MenuItem | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [toast, setToast] = useState<ToastData | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    listMenuItems()
      .then((nextItems) => { if (mounted) { setItems(nextItems); setLoadError(""); } })
      .catch((reason: unknown) => { if (!mounted) return; if (isUnauthorized(reason)) clearSession(); else setLoadError(getApiErrorMessage(reason, "We could not load your menu right now.")); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [clearSession]);

  useEffect(() => {
    if (!toast) return undefined;
    const timeout = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const visibleItems = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return items.filter((item) => (!normalizedSearch || item.name.toLowerCase().includes(normalizedSearch)) && (dayFilter === "all" || item.day_of_week === dayFilter) && (mealTypeFilter === "all" || item.meal_type === mealTypeFilter) && (availabilityFilter === "all" || (availabilityFilter === "available" ? item.availability : !item.availability)));
  }, [availabilityFilter, dayFilter, items, mealTypeFilter, search]);

  function showToast(message: string, kind: ToastKind = "success") { setToast({ id: Date.now(), kind, message }); }

  function setBusy(id: number, busy: boolean) {
    setBusyIds((current) => { const next = new Set(current); if (busy) next.add(id); else next.delete(id); return next; });
  }

  async function handleCreate(payload: CreateMenuItemPayload | UpdateMenuItemPayload) {
    if (!("name" in payload)) return;
    setSubmitting(true);
    try {
      const created = await createMenuItem(payload);
      setItems((current) => [created, ...current]);
      setModal(null);
      showToast("Menu item added.");
    } catch (reason: unknown) { if (isUnauthorized(reason)) clearSession(); throw reason; }
    finally { setSubmitting(false); }
  }

  async function handleEdit(payload: CreateMenuItemPayload | UpdateMenuItemPayload) {
    if (!modal?.item || "name" in payload) return;
    setSubmitting(true);
    try {
      const updated = await updateMenuItem(modal.item.id, payload);
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
      setModal(null);
      showToast("Menu item updated.");
    } catch (reason: unknown) { if (isUnauthorized(reason)) clearSession(); throw reason; }
    finally { setSubmitting(false); }
  }

  async function handleToggleAvailability(item: MenuItem) {
    const nextAvailability = !item.availability;
    setBusy(item.id, true);
    setItems((current) => current.map((candidate) => candidate.id === item.id ? { ...candidate, availability: nextAvailability } : candidate));
    try {
      const updated = await updateMenuItemAvailability(item.id, nextAvailability);
      setItems((current) => current.map((candidate) => candidate.id === updated.id ? updated : candidate));
      showToast(`Availability changed to ${nextAvailability ? "available" : "sold out"}.`);
    } catch (reason: unknown) {
      setItems((current) => current.map((candidate) => candidate.id === item.id ? { ...candidate, availability: item.availability } : candidate));
      if (isUnauthorized(reason)) clearSession();
      showToast(getApiErrorMessage(reason, "We could not change availability."), "error");
    } finally { setBusy(item.id, false); }
  }

  async function handleDelete() {
    if (!deleteItem) return;
    const item = deleteItem;
    setBusy(item.id, true);
    try {
      await deactivateMenuItem(item.id);
      setItems((current) => current.filter((candidate) => candidate.id !== item.id));
      setDeleteItem(null);
      setDeleteError("");
      showToast("Menu item deleted.");
    } catch (reason: unknown) {
      if (isUnauthorized(reason)) clearSession();
      setDeleteError(getApiErrorMessage(reason, "We could not delete this menu item."));
    } finally { setBusy(item.id, false); }
  }

  function retryLoad() { window.location.reload(); }

  return <div>
    <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end"><div><p className="text-sm font-semibold uppercase tracking-widest text-teal-600">Operations</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-ink">Menu management</h1><p className="mt-2 text-sm text-slate-500">Keep scheduled meals, prices, and availability up to date.</p></div><button type="button" className="rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-teal-700 focus:outline-none focus:ring-4 focus:ring-teal-200" onClick={() => setModal({ mode: "create" })}>Add menu item</button></div>
    <section aria-label="Menu filters" className="mt-8 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5"><div className="grid gap-4 md:grid-cols-[1.5fr_1fr_1fr_1fr]"><div><label htmlFor="menu-search" className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">Search by name</label><input id="menu-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search menu items" className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100" /></div><div><label htmlFor="day-filter" className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">Day</label><select id="day-filter" value={dayFilter} onChange={(event) => setDayFilter(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100"><option value="all">All days</option>{DAYS.map((day) => <option key={day}>{day}</option>)}</select></div><div><label htmlFor="meal-type-filter" className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">Meal type</label><select id="meal-type-filter" value={mealTypeFilter} onChange={(event) => setMealTypeFilter(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm capitalize outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100"><option value="all">All meal types</option><option value="breakfast">Breakfast</option><option value="lunch">Lunch</option><option value="dinner">Dinner</option></select></div><div><label htmlFor="availability-filter" className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">Availability</label><select id="availability-filter" value={availabilityFilter} onChange={(event) => setAvailabilityFilter(event.target.value as AvailabilityFilter)} className="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100"><option value="all">All availability</option><option value="available">Available</option><option value="sold_out">Sold out</option></select></div></div></section>
    <div className="mt-8">{loading ? <LoadingCards /> : loadError ? <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700"><p className="font-semibold">Something went wrong</p><p className="mt-2">{loadError}</p><button type="button" className="mt-4 rounded-lg bg-rose-600 px-4 py-2 font-semibold text-white hover:bg-rose-700" onClick={retryLoad}>Try again</button></div> : items.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center shadow-sm"><p className="text-sm font-semibold uppercase tracking-widest text-teal-600">Your menu</p><h2 className="mt-3 text-2xl font-bold text-ink">No menu items yet</h2><p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-500">Add your first scheduled meal to start building the menu customers can order from.</p><button type="button" className="mt-6 rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white hover:bg-teal-700" onClick={() => setModal({ mode: "create" })}>Add your first item</button></div> : visibleItems.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center shadow-sm"><h2 className="text-xl font-bold text-ink">No matching menu items</h2><p className="mt-2 text-sm text-slate-500">Try a different search term or clear one of the filters.</p></div> : <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{visibleItems.map((item) => <MenuItemCard key={item.id} item={item} busy={busyIds.has(item.id)} onEdit={(selected) => setModal({ mode: "edit", item: selected })} onDelete={(selected) => { setDeleteError(""); setDeleteItem(selected); }} onToggleAvailability={(selected) => void handleToggleAvailability(selected)} />)}</div>}</div>
    {modal && <MenuItemModal mode={modal.mode} item={modal.item} submitting={submitting} onClose={() => { if (!submitting) setModal(null); }} onSubmit={modal.mode === "create" ? handleCreate : handleEdit} />}
    {deleteItem && <ConfirmDialog title="Delete menu item?" message={`${deleteItem.name} will be soft-deleted and removed from this list. Historical orders will remain unchanged.`} confirmLabel="Delete menu item" confirming={busyIds.has(deleteItem.id)} error={deleteError} onConfirm={() => void handleDelete()} onClose={() => { if (!busyIds.has(deleteItem.id)) { setDeleteItem(null); setDeleteError(""); } }} />}
    {toast && <Toast toast={toast} onClose={() => setToast(null)} />}
  </div>;
}
