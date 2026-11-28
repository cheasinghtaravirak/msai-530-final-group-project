# Inventory API

How many units of each SKU are in each branch, and why that number changed (design doc §4.3, §5.3, §6.2 S3, §6.3 E1/E2/E5/E6/E7/E8).

Conventions from `docs/implementation-plan.md` §3 apply to every endpoint:

- Through the gateway the prefix is `/api/inventory`. The service itself serves `/stock`, with no trailing slash.
- JSON is `snake_case`. Timestamps are ISO 8601 in `Asia/Phnom_Penh`. Quantities are integers.
- Lists are paginated with `?page=&page_size=` and return `{"results": [], "count": n}`.
- Errors are `{"error": {"code": "...", "message": "...", "details": {}}}`.
- Calls send `Authorization: Bearer <JWT>`. A manager can act only on branches in their token.

Every change to `stock_level` writes one `stock_movement` row in the same transaction, and publishes `stock.adjusted`. `on_hand` may go negative: a sale is never refused because the count is wrong.

The **Phase** column says which phase of the implementation plan builds the endpoint. Transfers are deferred (design doc §13.2). Their tables exist, but the endpoints are built only if time allows.

| Method and path | Phase | Roles |
|---|---|---|
| `GET /health` | 1 (built) | none |
| `GET /refs/branches` | 1 (built) | `HQ_ADMIN`, `BRANCH_MANAGER` |
| `GET /stock?branch_id=&sku=&low_only=` | 3 | `BRANCH_MANAGER` |
| `GET /stock/{branch_id}/{sku}/movements` | 3 | `BRANCH_MANAGER` |
| `POST /adjustments` | 3 | `BRANCH_MANAGER` |
| `POST /receipts` | 3 ad hoc, 4 against a PO | `BRANCH_MANAGER` |
| `GET /purchase-orders?branch_id=&status=` | 4 | `BRANCH_MANAGER` |
| `GET /transfers`, `POST /transfers` | deferred | `BRANCH_MANAGER` |
| `POST /transfers/{transfer_id}/ship` | deferred | `BRANCH_MANAGER` |
| `POST /transfers/{transfer_id}/receive` | deferred | `BRANCH_MANAGER` |

## GET /refs/branches

Debug view of the `branch_ref` copy fed by `branch.upserted`: `{"results": [{"branch_id", "name", "status", "updated_at"}], "count": n}`.

## GET /stock

`?branch_id=BR-04` lists the branch's stock, paginated. `sku` narrows it to one SKU. `low_only=true` keeps only low rows.

```json
{"results": [{"sku": "COKE-330", "name": "Coca-Cola 330 ml", "on_hand": 42, "on_order": 48}], "count": 1}
```

## GET /stock/{branch_id}/{sku}/movements

The ledger for one SKU at one branch, newest first, paginated:

```json
{
  "results": [
    {
      "movement_id": "…",
      "qty_delta": -2,
      "reason": "SALE",
      "source_ref": "6f1c2a3e-…",
      "source_line": 1,
      "note": "",
      "created_by": null,
      "occurred_at": "2026-11-26T14:03:24+07:00"
    }
  ],
  "count": 1
}
```

`reason` is `SALE`, `REFUND`, `RECEIPT`, `ADJUST`, `TRANSFER_OUT` or `TRANSFER_IN`. `source_ref` is the order, receipt or transfer ID. `created_by` is the user for manual changes and `null` for changes made by an event.

## POST /adjustments

```json
{"branch_id": "BR-04", "sku": "COKE-330", "qty_delta": -3, "note": "Count after breakage"}
```

`qty_delta` is non-zero. Writes an `ADJUST` movement, updates `on_hand`, and returns the new stock row.

## POST /receipts

```json
{"po_id": "…", "branch_id": "BR-04", "lines": [{"sku": "COKE-330", "qty": 48}]}
```

- `po_id` is `null` for an ad hoc receipt (Phase 3).
- Against a PO (Phase 4), a receipt may be partial or full. Each line raises `qty_received` on the PO line, raises `on_hand` and lowers `on_order`. The PO becomes `PARTIAL`, or `RECEIVED` when every line is fully received.
- Writes one `RECEIPT` movement per line. `received_by` comes from the token. Returns the receipt with its `receipt_id`.

## GET /purchase-orders

`?branch_id=BR-04&status=OPEN` lists POs, newest first, paginated. `status` is `OPEN`, `PARTIAL`, `RECEIVED` or `CANCELLED`.

```json
{
  "results": [
    {
      "po_id": "…",
      "branch_id": "BR-04",
      "supplier_id": "…",
      "recommendation_id": "…",
      "status": "OPEN",
      "created_at": "2026-11-27T00:41:10+07:00",
      "lines": [{"sku": "COKE-330", "qty_ordered": 48, "qty_received": 0}]
    }
  ],
  "count": 1
}
```

## Transfers (deferred)

`POST /transfers {from_branch_id, to_branch_id, lines: [{sku, qty}]}` creates a transfer in `REQUESTED`. `ship` writes `TRANSFER_OUT` movements at the source and sets `SHIPPED`. `receive` writes `TRANSFER_IN` movements at the destination and sets `RECEIVED`.

## Events

| Event | Direction | Phase | Effect |
|---|---|---|---|
| `branch.upserted` (E1) | consumes | 1 (built) | Upsert `branch_ref` |
| `product.upserted` (E2) | consumes | 2 (built) | Upsert `sku_ref`. `active` is `status == "ACTIVE"`. |
| `order.completed` (E5) | consumes | 3 | One `SALE` movement per line (`-qty`) |
| `order.refunded` (E6) | consumes | 3 | One `REFUND` movement per line (`+qty`) |
| `replenishment.approved` (E8) | consumes | 4 (REORDER), deferred (TRANSFER) | REORDER: create a PO and raise `on_order`. TRANSFER: create a transfer in `REQUESTED`. A repeat is blocked by `UNIQUE recommendation_id`. |
| `stock.adjusted` (E7) | publishes | 3 | After every stock change. Payload in design doc §6.3. |
