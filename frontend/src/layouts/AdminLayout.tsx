import { useState } from "react";
import { Outlet } from "react-router-dom";

import { Sidebar } from "../components/Sidebar";

export function AdminLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return <div className="min-h-screen bg-[#f7faf9] lg:flex"><Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} /><div className="min-w-0 flex-1"><header className="flex h-20 items-center border-b border-slate-200 bg-white px-5 lg:hidden"><button aria-label="Open navigation" className="rounded-lg p-2 text-xl text-ink hover:bg-slate-100" onClick={() => setSidebarOpen(true)}>☰</button><span className="ml-3 font-bold text-ink">TiffinAI</span></header><main className="mx-auto max-w-7xl p-5 sm:p-8"><Outlet /></main></div></div>;
}