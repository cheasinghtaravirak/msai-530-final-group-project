// Run: npx esbuild scripts/check-sale.ts --bundle --platform=node --log-level=warning | node
import assert from "node:assert/strict";

import { IDLE, saleReducer, type Sale, type SaleAction } from "../src/features/pos/sale";

const cola = { sku: "TEST-COLA", name: "Test cola", unitCents: 170 };
const bread = { sku: "TEST-BREAD", name: "Test bread", unitCents: 150 };
const run = (sale: Sale, ...actions: SaleAction[]) => actions.reduce(saleReducer, sale);

const submitted = run(
  IDLE,
  { type: "add", line: cola, newOrderId: "order-1" },
  { type: "tender", tender: { method: "CARD" } },
  { type: "submit" },
);
const unconfirmed = saleReducer(submitted, { type: "unanswered", message: "Cannot reach the server" });
assert.equal(unconfirmed.step, "unconfirmed");

const edits: SaleAction[] = [
  { type: "add", line: bread, newOrderId: "order-2" },
  { type: "add", line: cola, newOrderId: "order-2" },
  { type: "set_qty", sku: cola.sku, qty: 3 },
  { type: "remove", sku: cola.sku },
  { type: "clear" },
  { type: "tender", tender: { method: "CASH" } },
];
for (const edit of edits) {
  assert.equal(saleReducer(unconfirmed, edit), unconfirmed, `${edit.type} is refused while the outcome is unknown`);
}

const retried = saleReducer(unconfirmed, { type: "submit" });
assert.equal(retried.step, "submitting");
assert.equal(retried.step === "submitting" && retried.orderId, "order-1", "a retry reuses the order id");
assert.equal(saleReducer(retried, { type: "unanswered", message: "Service unavailable" }).step, "unconfirmed");

const refused = saleReducer(retried, { type: "failed", failure: { kind: "prices_changed" } });
assert.equal(refused.step, "cart", "a definite 4xx unlocks the cart");
const edited = saleReducer(refused, { type: "add", line: bread, newOrderId: "order-2" });
assert.equal(edited.step === "cart" && edited.lines.length, 2, "an unlocked cart can be edited again");

const order = { order_id: "order-1", total_amount: "1.70" } as Extract<Sale, { step: "receipt" }>["order"];
const receipt = saleReducer(retried, { type: "succeeded", order, replayed: true });
assert.equal(receipt.step === "receipt" && receipt.replayed, true, "a retry that finds the sale shows its receipt");

console.log("sale reducer: all checks passed");
