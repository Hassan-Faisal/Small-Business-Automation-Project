import { useEffect, useState, type FormEvent } from "react";

import type { CreateMenuItemPayload, DayOfWeek, MealType, MenuItem, UpdateMenuItemPayload } from "../types/menu";
import { getApiErrorMessage } from "../utils/errors";

const DAYS: DayOfWeek[] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const MEAL_TYPES: MealType[] = ["breakfast", "lunch", "dinner"];
type MenuFormState = { name: string; description: string; price: string; day_of_week: DayOfWeek; meal_type: MealType; availability: boolean };
type MenuFormErrors = Partial<Record<keyof MenuFormState, string>>;

interface MenuItemModalProps {
  mode: "create" | "edit";
  item?: MenuItem;
  submitting: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateMenuItemPayload | UpdateMenuItemPayload) => Promise<void>;
}

function initialForm(item?: MenuItem): MenuFormState {
  return { name: item?.name ?? "", description: item?.description ?? "", price: item ? String(item.price) : "", day_of_week: item?.day_of_week ?? "Monday", meal_type: item?.meal_type ?? "lunch", availability: item?.availability ?? true };
}

function validateForm(form: MenuFormState, mode: MenuItemModalProps["mode"]): MenuFormErrors {
  const errors: MenuFormErrors = {};
  if (mode === "create" && !form.name.trim()) errors.name = "Enter a menu item name.";
  if (!form.price.trim()) errors.price = "Enter a price.";
  else if (!/^\d+(\.\d{1,2})?$/.test(form.price.trim()) || Number(form.price) <= 0) errors.price = "Enter a price greater than zero with up to two decimal places.";
  return errors;
}

export function MenuItemModal({ mode, item, submitting, onClose, onSubmit }: MenuItemModalProps) {
  const [form, setForm] = useState(() => initialForm(item));
  const [errors, setErrors] = useState<MenuFormErrors>({});
  const [requestError, setRequestError] = useState("");
  const isCreate = mode === "create";

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) { if (event.key === "Escape" && !submitting) onClose(); }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, submitting]);

  function updateField<Key extends keyof MenuFormState>(field: Key, value: MenuFormState[Key]) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setRequestError("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = validateForm(form, mode);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    try {
      if (isCreate) await onSubmit({ name: form.name.trim(), description: form.description.trim() || null, price: form.price.trim(), day_of_week: form.day_of_week, meal_type: form.meal_type, availability: form.availability, is_active: true });
      else await onSubmit({ description: form.description.trim() || null, price: form.price.trim(), availability: form.availability });
    } catch (reason: unknown) { setRequestError(getApiErrorMessage(reason, `We could not ${isCreate ? "add" : "update"} this menu item.`)); }
  }

  const title = isCreate ? "Add menu item" : "Edit menu item";
  return <div className="fixed inset-0 z-40 overflow-y-auto bg-ink/40 px-5 py-8" role="presentation"><div role="dialog" aria-modal="true" aria-labelledby="menu-modal-title" className="mx-auto w-full max-w-xl rounded-2xl bg-white p-6 shadow-soft sm:p-8"><div className="flex items-start justify-between gap-4"><div><p className="text-sm font-semibold uppercase tracking-widest text-teal-600">Menu management</p><h2 id="menu-modal-title" className="mt-2 text-2xl font-bold text-ink">{title}</h2><p className="mt-2 text-sm text-slate-500">{isCreate ? "Add an offering to your scheduled menu." : "Update the details that customers see."}</p></div><button type="button" disabled={submitting} aria-label="Close dialog" className="rounded-lg p-2 text-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50" onClick={onClose}>×</button></div>
    <form className="mt-7 space-y-5" onSubmit={(event) => void handleSubmit(event)} noValidate>
      {isCreate && <div><label htmlFor="menu-name" className="mb-2 block text-sm font-semibold text-ink">Name</label><input id="menu-name" value={form.name} onChange={(event) => updateField("name", event.target.value)} className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100" placeholder="Chicken biryani" autoFocus />{errors.name && <p className="mt-2 text-sm text-rose-600">{errors.name}</p>}</div>}
      <div><label htmlFor="menu-description" className="mb-2 block text-sm font-semibold text-ink">Description</label><textarea id="menu-description" rows={3} value={form.description} onChange={(event) => updateField("description", event.target.value)} className="w-full resize-y rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100" placeholder="A short description of the meal" /></div>
      <div className="grid gap-5 sm:grid-cols-2"><div><label htmlFor="menu-price" className="mb-2 block text-sm font-semibold text-ink">Price</label><div className="relative"><span className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-sm text-slate-500">PKR</span><input id="menu-price" inputMode="decimal" value={form.price} onChange={(event) => updateField("price", event.target.value)} className="w-full rounded-xl border border-slate-300 py-3 pl-14 pr-4 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100" placeholder="450.00" /></div>{errors.price && <p className="mt-2 text-sm text-rose-600">{errors.price}</p>}</div>{isCreate && <div><label htmlFor="menu-day" className="mb-2 block text-sm font-semibold text-ink">Day</label><select id="menu-day" value={form.day_of_week} onChange={(event) => updateField("day_of_week", event.target.value as DayOfWeek)} className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100">{DAYS.map((day) => <option key={day}>{day}</option>)}</select></div>}</div>
      {isCreate && <div><label htmlFor="menu-meal-type" className="mb-2 block text-sm font-semibold text-ink">Meal type</label><select id="menu-meal-type" value={form.meal_type} onChange={(event) => updateField("meal_type", event.target.value as MealType)} className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm capitalize outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-100">{MEAL_TYPES.map((mealType) => <option key={mealType} value={mealType}>{mealType}</option>)}</select></div>}
      <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-4 py-3"><input type="checkbox" checked={form.availability} onChange={(event) => updateField("availability", event.target.checked)} className="h-4 w-4 accent-teal-600" /><span><span className="block text-sm font-semibold text-ink">Available</span><span className="mt-1 block text-xs text-slate-500">Customers can order this item when it is available.</span></span></label>
      {requestError && <p role="alert" className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{requestError}</p>}
      <div className="flex justify-end gap-3 border-t border-slate-100 pt-5"><button type="button" disabled={submitting} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60" onClick={onClose}>Cancel</button><button type="submit" disabled={submitting} className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60">{submitting ? "Saving…" : isCreate ? "Add menu item" : "Save changes"}</button></div>
    </form></div></div>;
}
