import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "../components/ProtectedRoute";
import { AdminLayout } from "../layouts/AdminLayout";
import { ComingSoonPage } from "../pages/ComingSoonPage";
import { DashboardPage } from "../pages/DashboardPage";
import { LoginPage } from "../pages/LoginPage";

export function AppRoutes() {
  return <Routes><Route path="/login" element={<LoginPage />} /><Route element={<ProtectedRoute />}><Route element={<AdminLayout />}><Route path="/dashboard" element={<DashboardPage />} /><Route path="/orders" element={<ComingSoonPage title="Orders" />} /><Route path="/menu" element={<ComingSoonPage title="Menu" />} /><Route path="/customers" element={<ComingSoonPage title="Customers" />} /><Route path="/subscriptions" element={<ComingSoonPage title="Subscriptions" />} /><Route path="/settings" element={<ComingSoonPage title="Settings" />} /></Route></Route><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes>;
}