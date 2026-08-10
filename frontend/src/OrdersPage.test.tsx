import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./api/client";
import { AuthProvider } from "./contexts/AuthContext";
import { AppRoutes } from "./routes/AppRoutes";

vi.mock("./api/client", () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

const apiMock = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
};

const admin = {
  id: 1, full_name: "Ayesha Khan", email: "owner@example.com", role: "owner",
  is_active: true, created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z", last_login_at: null,
};

const listItem = {
  id: 1, order_number: "ORD-100", customer_phone: "+923001234567",
  status: "draft", total_amount: "650.00", created_at: "2026-08-02T08:30:00Z",
  updated_at: "2026-08-02T08:30:00Z", item_count: 2, delivery_provider: null,
};

const detail = {
  id: 1, order_number: "ORD-100", customer_phone: "+923001234567", status: "draft",
  total_amount: "650.00", delivery_address: "House 1, Main Street",
  customer_notes: "Less spicy", internal_note: null,
  created_at: "2026-08-02T08:30:00Z", updated_at: "2026-08-02T08:30:00Z",
  confirmed_at: null, completed_at: null, cancelled_at: null,
  estimated_delivery_minutes: null, delivery_provider: null, rider_note: null,
  items: [{ product_name: "Chicken Biryani", quantity: 2, unit_price: "325.00", subtotal: "650.00" }],
};

function renderOrders() {
  return render(<MemoryRouter initialEntries={["/orders"]}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter>);
}

function setupApi(orderDetail = detail) {
  apiMock.get.mockImplementation((url: string) => {
    if (url.endsWith("/me")) return Promise.resolve({ data: admin });
    if (url === "/admin/orders") return Promise.resolve({ data: { items: [listItem], page: 1, page_size: 10, total: 1, pages: 1 } });
    if (url === "/admin/orders/1") return Promise.resolve({ data: orderDetail });
    return Promise.reject(new Error("Unexpected GET"));
  });
}

beforeEach(() => {
  apiMock.get.mockReset();
  apiMock.post.mockReset();
  apiMock.patch.mockReset();
});

describe("OrdersPage", () => {
  it("renders orders and an empty state", async () => {
    setupApi();
    const firstRender = renderOrders();
    expect((await screen.findAllByText("ORD-100")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("+923001234567")).length).toBeGreaterThan(0);
    firstRender.unmount();

    apiMock.get.mockImplementation((url: string) => {
      if (url.endsWith("/me")) return Promise.resolve({ data: admin });
      return Promise.resolve({ data: { items: [], page: 1, page_size: 10, total: 0, pages: 0 } });
    });
    renderOrders();
    expect(await screen.findByText("No orders yet")).toBeInTheDocument();
  });

  it("sends combined filters and paginates", async () => {
    apiMock.get.mockImplementation((url: string) => {
      if (url.endsWith("/me")) return Promise.resolve({ data: admin });
      return Promise.resolve({ data: { items: [listItem], page: 1, page_size: 10, total: 11, pages: 2 } });
    });
    renderOrders();
    await screen.findAllByText("ORD-100");
    await userEvent.selectOptions(screen.getByLabelText("Status"), "confirmed");
    await userEvent.type(screen.getByLabelText("Search"), "ORD");
    await waitFor(() => expect(apiMock.get).toHaveBeenLastCalledWith("/admin/orders", expect.objectContaining({
      params: expect.objectContaining({ status: "confirmed", search: "ORD", page: 1 }),
    })));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(apiMock.get).toHaveBeenLastCalledWith("/admin/orders", expect.objectContaining({
      params: expect.objectContaining({ page: 2 }),
    })));
  });

  it("opens details, shows only valid next actions, and performs a successful transition", async () => {
    setupApi();
    const confirmedDetail = { ...detail, status: "confirmed", confirmed_at: "2026-08-02T09:00:00Z" };
    apiMock.patch.mockResolvedValue({ data: confirmedDetail });
    renderOrders();
    await userEvent.click(await screen.findByRole("button", { name: "ORD-100" }));
    expect(await screen.findByRole("dialog", { name: /ORD-100/i })).toHaveTextContent("House 1, Main Street");
    expect(screen.getByText("Chicken Biryani")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel order" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start preparing" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(apiMock.patch).toHaveBeenCalledWith("/admin/orders/1/status", { status: "confirmed" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Confirm completed.");
  });

  it("requires confirmation for cancellation and never exposes actions for completed orders", async () => {
    setupApi();
    renderOrders();
    await userEvent.click(await screen.findByRole("button", { name: "ORD-100" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel order" }));
    expect(screen.getByRole("dialog", { name: "Cancel order ORD-100?" })).toBeInTheDocument();
    expect(apiMock.patch).not.toHaveBeenCalled();
    await userEvent.click(within(screen.getByRole("dialog", { name: "Cancel order ORD-100?" })).getByRole("button", { name: "Cancel order" }));
    expect(apiMock.patch).toHaveBeenCalledWith("/admin/orders/1/status", { status: "cancelled" });

    apiMock.get.mockImplementation((url: string) => {
      if (url.endsWith("/me")) return Promise.resolve({ data: admin });
      if (url === "/admin/orders") return Promise.resolve({ data: { items: [{ ...listItem, status: "completed" }], page: 1, page_size: 10, total: 1, pages: 1 } });
      return Promise.resolve({ data: { ...detail, status: "completed" } });
    });
    renderOrders();
    await userEvent.click(await screen.findByRole("button", { name: "ORD-100" }));
    expect(screen.queryByText("Next actions")).not.toBeInTheDocument();
  });

  it("updates delivery details and keeps failed transitions visible as errors", async () => {
    setupApi();
    apiMock.patch.mockImplementation((url: string) => url.endsWith("/delivery")
      ? Promise.resolve({ data: { ...detail, delivery_provider: "bykea", estimated_delivery_minutes: 35 } })
      : Promise.reject({ isAxiosError: true, response: { status: 409, data: { detail: "Cannot transition order." } } }));
    renderOrders();
    await userEvent.click(await screen.findByRole("button", { name: "ORD-100" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot transition order.");

    await userEvent.selectOptions(screen.getByLabelText("Delivery provider"), "bykea");
    await userEvent.clear(screen.getByLabelText("Estimated delivery minutes"));
    await userEvent.type(screen.getByLabelText("Estimated delivery minutes"), "35");
    await userEvent.click(screen.getByRole("button", { name: "Save delivery details" }));
    await waitFor(() => expect(apiMock.patch).toHaveBeenCalledWith("/admin/orders/1/delivery", {
      delivery_provider: "bykea", estimated_delivery_minutes: 35,
    }));
  });

  it("redirects to login when the session is unauthenticated", async () => {
    const error = Object.assign(new Error("unauthorized"), { isAxiosError: true, response: { status: 401 } });
    apiMock.get.mockRejectedValue(error);
    renderOrders();
    expect(await screen.findByRole("heading", { name: /sign in to your dashboard/i })).toBeInTheDocument();
  });

  it("refreshes the order list in the background and cleans up polling", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      setupApi();
      const rendered = renderOrders();
      expect(await screen.findAllByText("ORD-100")).not.toHaveLength(0);
      const initialListCalls = apiMock.get.mock.calls.filter(([url]) => url === "/admin/orders").length;
      await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
      await waitFor(() => expect(apiMock.get.mock.calls.filter(([url]) => url === "/admin/orders").length).toBe(initialListCalls + 1));
      rendered.unmount();
      const callsAfterUnmount = apiMock.get.mock.calls.filter(([url]) => url === "/admin/orders").length;
      await act(async () => { await vi.advanceTimersByTimeAsync(40_000); });
      expect(apiMock.get.mock.calls.filter(([url]) => url === "/admin/orders").length).toBe(callsAfterUnmount);
    } finally {
      vi.useRealTimers();
    }
  });
});
