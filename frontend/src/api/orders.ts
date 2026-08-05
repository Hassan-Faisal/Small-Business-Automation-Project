import { api } from "./client";
import type {
  OrderDeliveryUpdatePayload,
  OrderDetail,
  OrderFilters,
  OrderListResponse,
  OrderStatusUpdatePayload,
} from "../types/order";
import { isOrderDetail, isOrderListResponse } from "../utils/validation";

const ORDERS_PATH = "/admin/orders";

export async function listOrders(filters: OrderFilters, page: number, pageSize = 10): Promise<OrderListResponse> {
  const params: Record<string, string | number> = { page, page_size: pageSize };
  for (const [key, value] of Object.entries(filters)) {
    if (value.trim()) params[key] = value.trim();
  }
  const response = await api.get<OrderListResponse>(ORDERS_PATH, { params });
  if (!isOrderListResponse(response.data)) throw new Error("Unexpected orders response");
  return response.data;
}

export async function getOrder(id: number): Promise<OrderDetail> {
  const response = await api.get<OrderDetail>(`${ORDERS_PATH}/${id}`);
  if (!isOrderDetail(response.data)) throw new Error("Unexpected order detail response");
  return response.data;
}

export async function updateOrderStatus(id: number, payload: OrderStatusUpdatePayload): Promise<OrderDetail> {
  const response = await api.patch<OrderDetail>(`${ORDERS_PATH}/${id}/status`, payload);
  if (!isOrderDetail(response.data)) throw new Error("Unexpected status update response");
  return response.data;
}

export async function updateOrderDelivery(id: number, payload: OrderDeliveryUpdatePayload): Promise<OrderDetail> {
  const response = await api.patch<OrderDetail>(`${ORDERS_PATH}/${id}/delivery`, payload);
  if (!isOrderDetail(response.data)) throw new Error("Unexpected delivery update response");
  return response.data;
}

