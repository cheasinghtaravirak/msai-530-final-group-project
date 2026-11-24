// Shapes from services/order, services/inventory and services/analytics API.md. Money is a 2-decimal string.

export interface Page<T> {
  results: T[];
  count: number;
}

export interface PosItem {
  sku: string;
  name: string;
  unit_price: string | null;
}

export type PaymentMethod = "CASH" | "CARD" | "QR";

export interface Payment {
  method: PaymentMethod;
  amount: string;
}

export interface OrderLine {
  line_no: number;
  sku: string;
  name: string;
  unit_price: string;
  qty: number;
  line_total: string;
}

export interface Order {
  order_id: string;
  branch_id: string;
  cashier_id: string;
  status: "COMPLETED" | "REFUNDED";
  total_amount: string;
  completed_at: string;
  sale_date: string;
  refunded_at: string | null;
  refund_date: string | null;
  lines: OrderLine[];
  payments: Payment[];
}

export interface StockRow {
  sku: string;
  name: string;
  on_hand: number;
  on_order: number;
  low: boolean;
}

export interface Movement {
  movement_id: string;
  qty_delta: number;
  reason: "SALE" | "REFUND" | "RECEIPT" | "ADJUST" | "TRANSFER_OUT" | "TRANSFER_IN";
  source_ref: string;
  source_line: number;
  note: string;
  created_by: string | null;
  occurred_at: string;
}

export interface SalesPeriod {
  period: string;
  branch_id: string;
  revenue: string;
  units: number;
  orders: number;
  avg_basket: string;
  status: string;
}
