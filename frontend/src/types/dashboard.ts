export interface TopSellingItem {
  name: string;
  quantity: number;
}

export interface RecentOrder {
  id: number;
  order_number: string;
  customer_phone: string;
  status: string;
  total_amount: string | number;
  created_at: string;
}

export interface DashboardSummary {
  today_orders: number;
  pending_orders: number;
  draft_orders: number;
  confirmed_orders: number;
  preparing_orders: number;
  ready_orders: number;
  rider_assigned_orders: number;
  out_for_delivery_orders: number;
  delivered_orders: number;
  completed_orders: number;
  cancelled_orders: number;
  today_revenue: string | number;
  active_subscriptions: number;
  total_customers: number;
  top_selling_item: TopSellingItem | null;
  recent_orders: RecentOrder[];
}