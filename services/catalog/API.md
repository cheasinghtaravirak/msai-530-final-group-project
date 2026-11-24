# Catalog API

What the company sells, at what price, and who supplies it (design doc §4.2, §5.2, §6.2 S2/S6, §6.3 E2–E4).

Conventions from `docs/implementation-plan.md` §3 apply to every endpoint:

- Through the gateway the prefix is `/api/catalog`. The service itself serves `/products`, with no trailing slash.
- JSON is `snake_case`. Money is a 2-decimal string (`"1.70"`). Dates are `YYYY-MM-DD`.
- Lists are paginated with `?page=&page_size=` (default 50, max 500) and return `{"results": [], "count": n}`.
- Errors are `{"error": {"code": "...", "message": "...", "details": {}}}`.
- Reads are for `HQ_ADMIN` and `BRANCH_MANAGER`. Writes are for `HQ_ADMIN`.

| Method and path | Phase | Roles |
|---|---|---|
| `GET /health` | 1 (built) | none |
| `GET /categories`, `POST /categories` | 2 (built) | read, HQ |
| `GET /products?q=&category_id=&status=`, `POST /products` | 2 (built) | read, HQ |
| `GET /products/{product_id}`, `PATCH /products/{product_id}` | 2 (built) | read, HQ |
| `GET /skus/{sku}` | 2 (built) | read |
| `PUT /prices/{sku}` | 2 (built) | HQ |
| `GET /prices/{sku}?branch_id=` (S6) | 2 (built) | service token, or any staff role for that branch |
| `GET /suppliers`, `POST /suppliers`, `PATCH /suppliers/{supplier_id}` | 2 (built) | HQ |
| `PUT /suppliers/{supplier_id}/skus/{sku}` | 2 (built) | HQ |

## Price rule

For a SKU at a branch on a date, take the latest `valid_from <= date` with `branch_scope = branch_id`. If there is none, take the latest with `branch_scope = ALL`. A branch price therefore beats a newer `ALL` price. The rule lives in `products/pricing.py`; Order applies the same rule to its cache in `caches/pricing.py`.

## Categories

`POST /categories {"name": "Beverages", "parent_id": null}` returns `{"category_id", "parent_id", "name"}`. Names are unique.

## Products and SKUs

A product is sold as one or more SKUs. Each SKU has its own display name, because a product sold in two sizes needs one per SKU at the till.

`GET /products?q=coca` matches the product name, brand, SKU code, or exact barcode. Each SKU carries `price`, today's `ALL` price, or `null`:

```json
{
  "results": [
    {
      "product_id": "…",
      "category_id": "…",
      "category": "Beverages",
      "name": "Coca-Cola",
      "brand": "",
      "status": "ACTIVE",
      "skus": [
        {"sku": "COKE-330", "name": "Coca-Cola 330 ml", "barcode": "8840000000011", "unit": "EA", "pack_size": 24, "price": "0.70"}
      ]
    }
  ],
  "count": 1
}
```

`POST /products` takes the same shape without `product_id`, `category` and `price`, with at least one SKU. `PATCH /products/{product_id}` takes any of `name`, `brand`, `category_id`, `status` (`ACTIVE` or `DISCONTINUED`) and `skus`. Each listed SKU is created or has all its fields replaced; SKUs not listed are left alone. A SKU code owned by another product returns 409 `SKU_TAKEN`, and a barcode used by another SKU returns 409 `BARCODE_TAKEN`.

Both publish `product.upserted` for every SKU of the product, plus `supplier_terms.changed` for each of its supplier terms, since that payload carries the SKU's `pack_size`.

`GET /skus/{sku}` returns the SKU with every price row, for the price edit dialog:

```json
{
  "sku": "COKE-330", "name": "Coca-Cola 330 ml", "barcode": "8840000000011", "unit": "EA", "pack_size": 24,
  "product_id": "…",
  "prices": [{"sku": "COKE-330", "branch_scope": "ALL", "valid_from": "2025-01-01", "amount": "0.70"}]
}
```

## Prices

`PUT /prices/{sku} {"branch_scope": "BR-01", "amount": "0.65", "valid_from": "2026-11-25"}` creates or replaces the row for that `(sku, branch_scope, valid_from)` and publishes `price.changed`. `branch_scope` is `ALL` or a branch ID. Returns the row.

`GET /prices/{sku}?branch_id=BR-01` (S6) returns today's price by the rule. Order calls it with `X-Service-Token` when a SKU is missing from its cache:

```json
{"sku": "COKE-330", "name": "Coca-Cola 330 ml", "barcode": "8840000000011", "amount": "0.70", "valid_from": "2025-01-01"}
```

An unknown SKU returns 404 `NOT_FOUND`. A SKU with no price for that branch today returns 404 `PRICE_NOT_FOUND`.

## Suppliers

`POST /suppliers {"name", "contact_email", "lead_time_days"}` returns the supplier with `supplier_id`. `PATCH /suppliers/{id}` changes any of those fields and republishes `supplier_terms.changed` for every SKU the supplier sells, since the payload carries `lead_time_days`.

`PUT /suppliers/{id}/skus/{sku} {"unit_cost": "0.49", "min_order_qty": 24, "is_preferred": true}` creates or replaces the terms and publishes `supplier_terms.changed`. A SKU has at most one preferred supplier: making one preferred demotes the other and publishes that change too.

## Events

All published through the outbox in the same transaction as the change.

| Event | Key | Payload | Published when |
|---|---|---|---|
| `product.upserted` (E2) | `sku` | `sku, product_id, barcode, name, brand, category_id, category_name, pack_size, status` | Product created or patched, once per SKU |
| `price.changed` (E3) | `sku:branch_scope:valid_from` | `sku, branch_scope, amount, currency, valid_from` | `PUT /prices/{sku}` |
| `supplier_terms.changed` (E4) | `supplier_id:sku` | `sku, supplier_id, is_preferred, lead_time_days, pack_size, min_order_qty, unit_cost` | Terms put, a supplier patched, a preferred supplier demoted, or the SKU's product patched |
