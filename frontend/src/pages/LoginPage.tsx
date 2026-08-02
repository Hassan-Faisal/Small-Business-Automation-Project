import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

export function LoginPage() {
  const { user, loading, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);


  if (loading) return <div className="flex min-h-screen items-center justify-center bg-teal-50 text-sm text-ink">Checking your session…</div>;
  if (user) return <Navigate to="/dashboard" replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) { setError("Enter your email and password to continue."); return; }
    setSubmitting(true);
    try { await login(email, password); } catch { setError("We could not sign you in. Check your details and try again."); } finally { setSubmitting(false); }
  }

  return <main className="flex min-h-screen items-center justify-center bg-teal-50 px-5 py-10"><div className="grid w-full max-w-5xl overflow-hidden rounded-3xl bg-white shadow-soft md:grid-cols-[1fr_1.1fr]"><section className="hidden bg-ink p-10 text-white md:flex md:flex-col md:justify-between"><div><p className="text-2xl font-bold">TiffinAI</p><p className="mt-2 text-sm text-teal-100">Owner dashboard</p></div><div><p className="text-4xl font-semibold leading-tight">A calmer way to run today’s orders.</p><p className="mt-5 max-w-sm text-sm leading-6 text-teal-100">See what is happening in your kitchen, keep an eye on recent orders, and make each day run smoothly.</p></div><p className="text-xs text-teal-200">Private workspace for business owners</p></section><section className="p-7 sm:p-12"><div className="mb-10 md:hidden"><p className="text-2xl font-bold text-ink">TiffinAI</p><p className="mt-1 text-sm text-slate-500">Owner dashboard</p></div><div className="max-w-md"><p className="text-sm font-semibold uppercase tracking-widest text-teal-600">Welcome back</p><h1 className="mt-3 text-3xl font-bold tracking-tight text-ink">Sign in to your dashboard</h1><p className="mt-3 text-sm leading-6 text-slate-500">Use the owner account created by your administrator.</p><form className="mt-8 space-y-5" onSubmit={handleSubmit} noValidate><div><label htmlFor="email" className="mb-2 block text-sm font-semibold text-ink">Email address</label><input id="email" type="email" autoComplete="username" value={email} onChange={(event) => { setEmail(event.target.value); setError(""); }} className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-teal-600 focus:ring-4 focus:ring-teal-100" placeholder="owner@example.com" /></div><div><label htmlFor="password" className="mb-2 block text-sm font-semibold text-ink">Password</label><div className="relative"><input id="password" type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(event) => { setPassword(event.target.value); setError(""); }} className="w-full rounded-xl border border-slate-300 px-4 py-3 pr-20 text-sm outline-none transition placeholder:text-slate-400 focus:border-teal-600 focus:ring-4 focus:ring-teal-100" placeholder="Enter your password" /><button type="button" className="absolute inset-y-0 right-3 text-xs font-semibold text-teal-700 hover:text-teal-900" onClick={() => setShowPassword((value) => !value)}>{showPassword ? "Hide" : "Show"}</button></div></div>{error && <p role="alert" className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}<button type="submit" disabled={submitting} className="w-full rounded-xl bg-teal-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 focus:outline-none focus:ring-4 focus:ring-teal-200 disabled:cursor-not-allowed disabled:opacity-60">{submitting ? "Signing in…" : "Sign in"}</button></form></div></section></div></main>;
}