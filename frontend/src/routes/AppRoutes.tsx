import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "../components/ProtectedRoute";
import { AdminLayout } from "../layouts/AdminLayout";
import { DashboardPage } from "../pages/DashboardPage";
import { LoginPage } from "../pages/LoginPage";
import { MenuManagementPage } from "../pages/MenuManagementPage";
import { OrdersPage } from "../pages/OrdersPage";

export function AppRoutes() {
  return <Routes><Route path="/login" element={<LoginPage />} /><Route element={<ProtectedRoute />}><Route element={<AdminLayout />}><Route path="/dashboard" element={<DashboardPage />} /><Route path="/orders" element={<OrdersPage />} /><Route path="/menu" element={<MenuManagementPage />} /></Route></Route><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes>;
}
