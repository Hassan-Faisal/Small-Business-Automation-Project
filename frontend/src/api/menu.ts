import { api } from "./client";
import type {
  CreateMenuItemPayload,
  MenuItem,
  MenuItemListResponse,
  UpdateMenuItemPayload,
} from "../types/menu";
import {
  isMenuItem,
  isMenuItemDeactivationResponse,
  isMenuItemListResponse,
} from "../utils/validation";

const MENU_ITEMS_PATH = "/admin/menu-items";
const PAGE_SIZE = 100;

export async function listMenuItems(): Promise<MenuItem[]> {
  const items: MenuItem[] = [];
  let page = 1;
  let total = 0;

  do {
    const response = await api.get<MenuItemListResponse>(MENU_ITEMS_PATH, {
      params: { page, page_size: PAGE_SIZE },
    });
    if (!isMenuItemListResponse(response.data)) throw new Error("Unexpected menu items response");
    items.push(...response.data.items);
    total = response.data.total;
    page += 1;
    if (response.data.items.length === 0) break;
  } while (items.length < total);

  return items;
}

export async function createMenuItem(payload: CreateMenuItemPayload): Promise<MenuItem> {
  const response = await api.post<MenuItem>(MENU_ITEMS_PATH, payload);
  if (!isMenuItem(response.data)) throw new Error("Unexpected created menu item response");
  return response.data;
}

export async function updateMenuItem(id: number, payload: UpdateMenuItemPayload): Promise<MenuItem> {
  const response = await api.patch<MenuItem>(`${MENU_ITEMS_PATH}/${id}`, payload);
  if (!isMenuItem(response.data)) throw new Error("Unexpected updated menu item response");
  return response.data;
}

export async function updateMenuItemAvailability(id: number, availability: boolean): Promise<MenuItem> {
  const response = await api.patch<MenuItem>(`${MENU_ITEMS_PATH}/${id}/availability`, { availability });
  if (!isMenuItem(response.data)) throw new Error("Unexpected availability response");
  return response.data;
}

export async function deactivateMenuItem(id: number): Promise<void> {
  const response = await api.delete<unknown>(`${MENU_ITEMS_PATH}/${id}`);
  if (!isMenuItemDeactivationResponse(response.data)) throw new Error("Unexpected delete response");
}
