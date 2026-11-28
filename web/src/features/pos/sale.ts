import type { Order, PaymentMethod } from "../../api/types";
import { fromCents, toCents } from "../../money";

export interface CartLine {
  sku: string;
  name: string;
  unitCents: number;
  qty: number;
}

export interface Tender {
  method: PaymentMethod;
  tendered: string;
}

export type Failure =
  { kind: "prices_changed" } | { kind: "item"; sku: string; message: string } | { kind: "error"; message: string };

export type Sale =
  | { step: "idle" }
  | { step: "cart"; orderId: string; lines: CartLine[]; tender: Tender; failure: Failure | null }
  | { step: "submitting"; orderId: string; lines: CartLine[]; tender: Tender }
  | { step: "receipt"; order: Order; tender: Tender; chargedCents: number; replayed: boolean };

export type SaleAction =
  | { type: "add"; line: Omit<CartLine, "qty">; newOrderId: string }
  | { type: "set_qty"; sku: string; qty: number }
  | { type: "remove"; sku: string }
  | { type: "clear" }
  | { type: "tender"; tender: Partial<Tender> }
  | { type: "submit" }
  | { type: "succeeded"; order: Order; replayed: boolean }
  | { type: "failed"; failure: Failure; prices?: { sku: string; unit_price: string }[] }
  | { type: "new_sale" };

export const IDLE: Sale = { step: "idle" };

export function cartTotal(lines: CartLine[]): number {
  return lines.reduce((sum, l) => sum + l.unitCents * l.qty, 0);
}

export function tenderedCents(tender: Tender): number | null {
  return toCents(tender.tendered);
}

export function canSubmit(sale: Sale): boolean {
  if (sale.step !== "cart") return false;
  if (sale.tender.method !== "CASH") return true;
  const cash = tenderedCents(sale.tender);
  return cash !== null && cash >= cartTotal(sale.lines);
}

export function orderRequest(sale: { orderId: string; lines: CartLine[]; tender: Tender }, branchId: string) {
  return {
    order_id: sale.orderId,
    branch_id: branchId,
    lines: sale.lines.map(({ sku, qty }) => ({ sku, qty })),
    payments: [{ method: sale.tender.method, amount: fromCents(cartTotal(sale.lines)) }],
  };
}

export function saleReducer(sale: Sale, action: SaleAction): Sale {
  switch (action.type) {
    case "add": {
      if (sale.step === "idle") {
        return {
          step: "cart",
          orderId: action.newOrderId,
          lines: [{ ...action.line, qty: 1 }],
          tender: { method: "CASH", tendered: "" },
          failure: null,
        };
      }
      if (sale.step !== "cart") return sale;
      const exists = sale.lines.some((l) => l.sku === action.line.sku);
      const lines = exists
        ? sale.lines.map((l) => (l.sku === action.line.sku ? { ...l, qty: l.qty + 1 } : l))
        : [...sale.lines, { ...action.line, qty: 1 }];
      return { ...sale, lines };
    }
    case "set_qty":
      if (sale.step !== "cart" || action.qty < 1) return sale;
      return { ...sale, lines: sale.lines.map((l) => (l.sku === action.sku ? { ...l, qty: action.qty } : l)) };
    case "remove": {
      if (sale.step !== "cart") return sale;
      const lines = sale.lines.filter((l) => l.sku !== action.sku);
      if (lines.length === 0) return IDLE;
      const failure = sale.failure?.kind === "item" && sale.failure.sku === action.sku ? null : sale.failure;
      return { ...sale, lines, failure };
    }
    case "clear":
      return sale.step === "cart" ? IDLE : sale;
    case "tender":
      return sale.step === "cart" ? { ...sale, tender: { ...sale.tender, ...action.tender } } : sale;
    case "submit":
      if (!canSubmit(sale) || sale.step !== "cart") return sale;
      return { step: "submitting", orderId: sale.orderId, lines: sale.lines, tender: sale.tender };
    case "succeeded":
      if (sale.step !== "submitting") return sale;
      return {
        step: "receipt",
        order: action.order,
        tender: sale.tender,
        chargedCents: cartTotal(sale.lines),
        replayed: action.replayed,
      };
    case "failed": {
      if (sale.step !== "submitting") return sale;
      const prices = new Map(action.prices?.map((p) => [p.sku, toCents(p.unit_price)]));
      const lines = sale.lines.map((l) => {
        const cents = prices.get(l.sku);
        return cents == null ? l : { ...l, unitCents: cents };
      });
      return { ...sale, step: "cart", lines, failure: action.failure };
    }
    case "new_sale":
      return sale.step === "receipt" ? IDLE : sale;
  }
}
