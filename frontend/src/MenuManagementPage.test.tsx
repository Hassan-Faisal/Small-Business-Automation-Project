import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./api/client";
import { AuthProvider } from "./contexts/AuthContext";
import { AppRoutes } from "./routes/AppRoutes";
import type { MenuItem } from "./types/menu";

vi.mock("./api/client", () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));

type ApiMock = {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;
const admin = { id: 1, full_name: "Ayesha Khan", email: "owner@example.com", role: "owner", is_active: true, created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z", last_login_at: null };
const chicken: MenuItem = { id: 1, name: "Chicken Biryani", description: "Fragrant basmati rice", price: "450.00", meal_type: "lunch", day_of_week: "Monday", availability: true, is_active: true };
const daal: MenuItem = { id: 2, name: "Daal Chawal", description: "Comforting lentils", price: "300.00", meal_type: "dinner", day_of_week: "Tuesday", availability: false, is_active: true };

function menuResponse(items: MenuItem[]) {
  return { data: { items, total: items.length, page: 1, page_size: 100 } };
}

function setupMenu(items: MenuItem[] = [chicken, daal]) {
  apiMock.get.mockImplementation((url: string) => {
    if (url === "/admin/auth/me") return Promise.resolve({ data: admin });
    return Promise.resolve(menuResponse(items));
  });
}

function renderMenu() {
  return render(<MemoryRouter initialEntries={["/menu"]}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter>);
}

beforeEach(() => {
  apiMock.get.mockReset();
  apiMock.post.mockReset();
  apiMock.patch.mockReset();
  apiMock.delete.mockReset();
});

describe("Menu management", () => {
  it("renders menu items and their operational details", async () => {
    setupMenu();
    renderMenu();

    expect(await screen.findByRole("heading", { name: /menu management/i })).toBeInTheDocument();
    expect(await screen.findByText("Chicken Biryani")).toBeInTheDocument();
    const chickenCard = screen.getByText("Chicken Biryani").closest("article");
    expect(chickenCard).not.toBeNull();
    if (!chickenCard) return;
    expect(within(chickenCard).getByText("Fragrant basmati rice")).toBeInTheDocument();
    expect(within(chickenCard).getByText("Monday")).toBeInTheDocument();
    expect(within(chickenCard).getByText("Lunch")).toBeInTheDocument();
    expect(within(chickenCard).getByText("Active")).toBeInTheDocument();
    expect(within(chickenCard).getAllByText("Available").length).toBeGreaterThan(0);
  });

  it("searches and applies day, meal type, and availability filters together", async () => {
    setupMenu();
    renderMenu();
    await screen.findByText("Chicken Biryani");

    await userEvent.type(screen.getByLabelText(/search by name/i), "daal");
    expect(screen.queryByText("Chicken Biryani")).not.toBeInTheDocument();
    expect(screen.getByText("Daal Chawal")).toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText(/search by name/i));
    await userEvent.selectOptions(screen.getByLabelText("Day"), "Tuesday");
    await userEvent.selectOptions(screen.getByLabelText("Meal type"), "dinner");
    await userEvent.selectOptions(screen.getByLabelText("Availability"), "sold_out");
    expect(screen.getByText("Daal Chawal")).toBeInTheDocument();
    expect(screen.queryByText("Chicken Biryani")).not.toBeInTheDocument();
  });

  it("creates a menu item through the POST endpoint", async () => {
    setupMenu([]);
    const created: MenuItem = { id: 3, name: "Kheer", description: "Rice pudding", price: "200.00", meal_type: "dinner", day_of_week: "Friday", availability: true, is_active: true };
    apiMock.post.mockResolvedValue({ data: created });
    renderMenu();
    await userEvent.click(await screen.findByRole("button", { name: /add your first item/i }));
    const dialog = screen.getByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Name"), "Kheer");
    await userEvent.type(within(dialog).getByLabelText("Description"), "Rice pudding");
    await userEvent.type(within(dialog).getByLabelText("Price"), "200.00");
    await userEvent.selectOptions(within(dialog).getByLabelText("Day"), "Friday");
    await userEvent.selectOptions(within(dialog).getByLabelText("Meal type"), "dinner");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add menu item" }));

    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith("/admin/menu-items", { name: "Kheer", description: "Rice pudding", price: "200.00", day_of_week: "Friday", meal_type: "dinner", availability: true, is_active: true }));
    expect(await screen.findByRole("status")).toHaveTextContent("Menu item added");
    expect(screen.getByText("Kheer")).toBeInTheDocument();
  });

  it("edits description, price, and availability through PATCH", async () => {
    setupMenu([chicken]);
    const updated = { ...chicken, description: "Extra fragrant basmati rice", price: "475.00", availability: false };
    apiMock.patch.mockResolvedValue({ data: updated });
    renderMenu();
    await userEvent.click(await screen.findByRole("button", { name: "Edit Chicken Biryani" }));
    const dialog = screen.getByRole("dialog");
    const description = within(dialog).getByLabelText("Description");
    await userEvent.clear(description);
    await userEvent.type(description, updated.description);
    const price = within(dialog).getByLabelText("Price");
    await userEvent.clear(price);
    await userEvent.type(price, updated.price);
    await userEvent.click(within(dialog).getByRole("checkbox"));
    await userEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(apiMock.patch).toHaveBeenCalledWith("/admin/menu-items/1", { description: updated.description, price: updated.price, availability: false }));
    expect(await screen.findByRole("status")).toHaveTextContent("Menu item updated");
    expect(screen.getByText("Extra fragrant basmati rice")).toBeInTheDocument();
  });

  it("confirms a soft delete and removes the item from the list", async () => {
    setupMenu([chicken]);
    apiMock.delete.mockResolvedValue({ data: { id: 1, message: "Menu item deactivated successfully.", availability: false, is_active: false } });
    renderMenu();
    await userEvent.click(await screen.findByRole("button", { name: "Delete Chicken Biryani" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/historical orders will remain unchanged/i)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete menu item" }));

    await waitFor(() => expect(apiMock.delete).toHaveBeenCalledWith("/admin/menu-items/1"));
    expect(await screen.findByRole("status")).toHaveTextContent("Menu item deleted");
    expect(screen.queryByText("Chicken Biryani")).not.toBeInTheDocument();
  });

  it("updates availability optimistically and confirms the server result", async () => {
    setupMenu([chicken]);
    const updated = { ...chicken, availability: false };
    let resolvePatch: ((value: { data: MenuItem }) => void) | undefined;
    apiMock.patch.mockImplementation(() => new Promise<{ data: MenuItem }>((resolve) => { resolvePatch = resolve; }));
    renderMenu();
    await userEvent.click(await screen.findByRole("button", { name: /mark sold out: chicken biryani/i }));
    expect(screen.getAllByText("Sold Out").length).toBeGreaterThan(0);
    resolvePatch?.({ data: updated });
    expect(await screen.findByRole("status")).toHaveTextContent("Availability changed to sold out");
    expect(apiMock.patch).toHaveBeenCalledWith("/admin/menu-items/1/availability", { availability: false });
  });
});
