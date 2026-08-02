import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./api/client";
import { AuthProvider } from "./contexts/AuthContext";
import { AppRoutes } from "./routes/AppRoutes";

vi.mock("./api/client", () => ({ api: { get: vi.fn(), post: vi.fn() } }));

const apiMock = api as unknown as { get: ReturnType<typeof vi.fn>; post: ReturnType<typeof vi.fn> };
const admin = { id: 1, full_name: "Ayesha Khan", email: "owner@example.com", role: "owner", is_active: true, created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z", last_login_at: null };
const summary = { today_orders: 3, pending_orders: 1, draft_orders: 1, confirmed_orders: 1, preparing_orders: 1, ready_orders: 0, rider_assigned_orders: 0, out_for_delivery_orders: 0, delivered_orders: 1, completed_orders: 0, cancelled_orders: 0, today_revenue: "1250.00", active_subscriptions: 4, total_customers: 9, top_selling_item: { name: "Chicken Biryani", quantity: 6 }, recent_orders: [{ id: 1, order_number: "ORD-100", customer_phone: "+923001234567", status: "delivered", total_amount: "650.00", created_at: "2026-08-02T08:30:00Z" }] };

function renderApp(path = "/login") {
  return render(<MemoryRouter initialEntries={[path]}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter>);
}

beforeEach(() => {
  apiMock.get.mockReset();
  apiMock.post.mockReset();
});

describe("TiffinAI admin dashboard", () => {
  it("validates the login form", async () => {
    apiMock.get.mockRejectedValue(new Error("unauthenticated"));
    renderApp();
    await screen.findByLabelText(/email address/i);
    await userEvent.click(screen.getByRole("button", { name: /^sign in$/i }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter your email and password");
    expect(apiMock.post).not.toHaveBeenCalled();
  });

  it("completes a successful login flow", async () => {
    apiMock.get.mockImplementation((url: string) => url.endsWith("/me") ? Promise.reject(new Error("unauthenticated")) : Promise.resolve({ data: summary }));
    apiMock.post.mockResolvedValue({ data: { message: "Login successful.", admin } });
    renderApp();
    await userEvent.type(await screen.findByLabelText(/email address/i), "owner@example.com");
    await userEvent.type(screen.getByLabelText(/^password$/i), "StrongPassword1");
    await userEvent.click(screen.getByRole("button", { name: /^sign in$/i }));
    expect(await screen.findByText(/today at a glance/i)).toBeInTheDocument();
    expect(apiMock.post).toHaveBeenCalledWith("/admin/auth/login", { email: "owner@example.com", password: "StrongPassword1" });
  });

  it("shows a generic failed-login message", async () => {
    apiMock.get.mockRejectedValue(new Error("unauthenticated"));
    apiMock.post.mockRejectedValue(new Error("invalid credentials"));
    renderApp();
    await userEvent.type(await screen.findByLabelText(/email address/i), "owner@example.com");
    await userEvent.type(screen.getByLabelText(/^password$/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /^sign in$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("We could not sign you in");
  });

  it("redirects unauthenticated protected routes to login", async () => {
    apiMock.get.mockRejectedValue(new Error("unauthenticated"));
    renderApp("/dashboard");
    expect(await screen.findByRole("heading", { name: /sign in to your dashboard/i })).toBeInTheDocument();
  });

  it("renders the dashboard summary and recent orders", async () => {
    apiMock.get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith("/me") ? admin : summary }));
    renderApp("/dashboard");
    expect(await screen.findByText(/today at a glance/i)).toBeInTheDocument();
    expect(screen.getByText("Chicken Biryani")).toBeInTheDocument();
    expect(screen.getByText("ORD-100")).toBeInTheDocument();
    expect(screen.getAllByText(/PKR/)).toHaveLength(2);
  });

  it("handles an unexpected dashboard response", async () => {
    apiMock.get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith("/me") ? admin : {} }));
    renderApp("/dashboard");
    expect(await screen.findByRole("alert")).toHaveTextContent("We could not load your dashboard");
  });

  it("shows the recent-orders empty state", async () => {
    apiMock.get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith("/me") ? admin : { ...summary, today_orders: 0, recent_orders: [], top_selling_item: null } }));
    renderApp("/dashboard");
    expect(await screen.findByText("No orders have been received yet.")).toBeInTheDocument();
  });

  it("logs out and returns to login", async () => {
    apiMock.get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith("/me") ? admin : summary }));
    apiMock.post.mockResolvedValue({ data: { message: "Logout successful." } });
    renderApp("/dashboard");
    await screen.findByText(/today at a glance/i);
    await userEvent.click(screen.getByRole("button", { name: /log out/i }));
    await waitFor(() => expect(screen.getByRole("heading", { name: /sign in to your dashboard/i })).toBeInTheDocument());
    expect(apiMock.post).toHaveBeenCalledWith("/admin/auth/logout");
  });
});