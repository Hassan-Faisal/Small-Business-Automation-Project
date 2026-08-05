export type OrderStatus =
  | "draft"
  | "confirmed"
  | "preparing"
  | "ready"
  | "rider_assigned"
  | "out_for_delivery"
  | "delivered"
  | "completed"
  | "cancelled";

export interface OrderListItem {
  id: number;
  order_number: string;
  customer_phone: string;
  status: string;
  total_amount: string | number;
  created_at: string;
  updated_at: string;
  item_count: number;
  delivery_provider: string | null;
}

export interface OrderListResponse {
  items: OrderListItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface OrderItemDetail {
  product_name: string;
  quantity: number;
  unit_price: string | number;
  subtotal: string | number;
}

export interface OrderDetail {
  id: number;
  order_number: string;
  customer_phone: string;
  status: string;
  total_amount: string | number;
  delivery_address: string;
  customer_notes: string | null;
  internal_note: string | null;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  estimated_delivery_minutes: number | null;
  delivery_provider: string | null;
  rider_note: string | null;
  items: OrderItemDetail[];
}

export interface OrderStatusUpdatePayload {
  status: OrderStatus;
}

export interface OrderDeliveryUpdatePayload {
  estimated_delivery_minutes?: number;
  delivery_provider?: "bykea" | "yango" | "uber" | "other";
  rider_note?: string;
  internal_note?: string;
}

export interface OrderFilters {
  status: string;
  date_from: string;
  date_to: string;
  customer_phone: string;
  order_number: string;
  search: string;
}

export const ORDER_STATUSES: readonly OrderStatus[] = [
  "draft",
  "confirmed",
  "preparing",
  "ready",
  "rider_assigned",
  "out_for_delivery",
  "delivered",
  "completed",
  "cancelled",
];

export const DELIVERY_PROVIDERS = [
  { value: "bykea", label: "Bykea" },
  { value: "yango", label: "Yango" },
  { value: "uber", label: "Uber" },
  { value: "other", label: "Other" },
] as const;

