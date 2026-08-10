import { NavLink } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

const links = [
  { to: "/dashboard", label: "Dashboard", end: true },
  { to: "/orders", label: "Orders" },
  { to: "/menu", label: "Menu" },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, logout } = useAuth();
  return (
    <>
      {open && <button aria-label="Close navigation" className="fixed inset-0 z-20 bg-ink/30 lg:hidden" onClick={onClose} />}
      <aside className={`fixed inset-y-0 left-0 z-30 flex w-72 flex-col bg-ink px-5 py-6 text-white transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center justify-between border-b border-white/10 pb-6">
          <div>
            <p className="text-xl font-bold tracking-tight">TiffinAI</p>
            <p className="mt-1 text-xs text-teal-100">Owner dashboard</p>
          </div>
          <button aria-label="Close navigation" className="rounded-lg p-2 text-teal-100 hover:bg-white/10 lg:hidden" onClick={onClose}>×</button>
        </div>
        <nav className="mt-8 space-y-1" aria-label="Main navigation">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} onClick={onClose} className={({ isActive }) => `block rounded-xl px-4 py-3 text-sm font-medium transition ${isActive ? "bg-white text-ink" : "text-teal-50 hover:bg-white/10"}`}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto border-t border-white/10 pt-5">
          <div className="mb-4 rounded-xl bg-white/10 px-4 py-3">
            <p className="truncate text-sm font-semibold">{user?.full_name}</p>
            <p className="mt-1 text-xs capitalize text-teal-100">{user?.role}</p>
          </div>
          <button className="w-full rounded-xl px-4 py-3 text-left text-sm font-medium text-teal-50 hover:bg-white/10" onClick={() => void logout()}>
            Log out
          </button>
        </div>
      </aside>
    </>
  );
}
