# Analytics API

Reports, forecasts, reorder suggestions and LLM briefings (design doc §4.5, §6.2 S5, §9). The web app reaches these through the gateway at `/api/analytics/...`; the paths below are what the service sees after the prefix is stripped.

**Phase** says when an endpoint is built. Until then, the front end uses mock data shaped like the examples here.

| Phase | Meaning |
|---|---|
| 1 | Live now |
| 3 | Selling and stock (Nov 26–27) |
| 4 | Reporting and AI (Nov 28–30) |
| Deferred | Design doc §13.2: built only if time allows |

## Conventions

- Every request carries `Authorization: Bearer <JWT>`. `HQ_ADMIN` sees every branch. `BRANCH_MANAGER` sees only the branches in its token. Asking for another branch returns 403. `CASHIER` has no Analytics access.
- JSON fields are `snake_case`. Money is a 2-decimal string (`"3.40"`). Forecast units are decimal strings too (`"12.40"`), because a forecast is not a whole number.
- Dates are `YYYY-MM-DD` (the branch-local day). Months are `YYYY-MM`. Timestamps are ISO 8601 with the `+07:00` offset.
- Lists return `{"results": [...], "count": n}`. Long lists take `?page=&page_size=` (default 50, max 500).
- Errors return `{"error": {"code": "...", "message": "...", "details": {}}}`. Common codes: `VALIDATION_ERROR` (400), `NOT_AUTHENTICATED` (401), `PERMISSION_DENIED` (403), `NOT_FOUND` (404), `ALREADY_DECIDED` (409).
- No trailing slashes.
- `status` on report rows is `PROVISIONAL` or `FINAL`. A day becomes `FINAL` 3 days after it ends. A month becomes `FINAL` when all its days are. Today is always `PROVISIONAL` and is read live from the facts.
- `branch_id` `ALL` means the whole company.

## Summary

| Method and path | Who | Phase |
|---|---|---|
| `GET /health` | anyone | 1 |
| `GET /dims/branches` | HQ, manager | 1 |
| `POST /jobs/{job}/run` | HQ | 1 (jobs are placeholders until Phases 3–4) |
| `GET /jobs/runs?job=&limit=` | HQ | 1 |
| `GET /jobs/runs/{run_id}` | HQ | 1 |
| `GET /reports/sales?scope=&branch_id=&grain=&from=&to=` | HQ, manager | 3 (`grain=day`, `scope=branch`), 4 (month, company) |
| `GET /reports/branches/compare?month=` | HQ | 4 |
| `GET /reports/top-skus?branch_id=&from=&to=&limit=` | HQ, manager | 4 |
| `GET /forecasts?branch_id=&sku=` | HQ, manager | 4 |
| `GET /recommendations?branch_id=&status=` | HQ, manager | 4 |
| `POST /recommendations/{id}/decision` | HQ, manager | 4 |
| `POST /recommendations/{id}/explain` | HQ, manager | 4 (Nov 30, LLM) |
| `GET /briefings?branch_id=&date=` | HQ, manager | 4 (Nov 30, LLM) |
| `GET /stock-policies?branch_id=` | HQ | 4 (seeded, minimal UI) |
| `PUT /stock-policies` | HQ | 4 (seeded, minimal UI) |
| `GET /anomalies?branch_id=&status=` | HQ, manager | Deferred |
| `PATCH /anomalies/{id}` | HQ, manager | Deferred |

## Phase 1: live now

### `GET /dims/branches`

Branches as Analytics knows them, copied from `branch.upserted`. A debugging view.

```json
{"results": [{"branch_id": "BR-01", "name": "Riverside", "region": "Phnom Penh", "status": "ACTIVE"}], "count": 1}
```

### `POST /jobs/{job}/run`

Queues a job. `job` is one of `reconcile`, `day_close`, `month_close`, `forecast`, `replenishment`, `briefing` or `nightly`. The scheduler picks it up within a few seconds. Returns 202 with the run. An unknown job returns 404 `UNKNOWN_JOB` with `details.jobs`.

```json
{
  "run_id": "0b6f…", "job": "nightly", "trigger": "MANUAL", "status": "QUEUED",
  "requested_by": "4c1e…", "message": "",
  "created_at": "2026-11-28T09:12:03+07:00", "started_at": null, "finished_at": null
}
```

`status` is `QUEUED`, `RUNNING`, `DONE` or `FAILED`.

### `GET /jobs/runs?job=&limit=`

The most recent runs first, `limit` defaults to 50 and is capped at 200. This endpoint does not paginate. It also returns the list of job names for the "Run now" buttons.

```json
{"results": [{"run_id": "0b6f…", "job": "nightly", "status": "DONE", "message": "day_close: …", "...": "..."}],
 "jobs": ["briefing", "day_close", "forecast", "month_close", "nightly", "reconcile", "replenishment"]}
```

### `GET /jobs/runs/{run_id}`

One run, same shape as above. 404 `NOT_FOUND` if it doesn't exist. The Jobs page polls this after "Run now".

## Reports

### `GET /reports/sales`

| Param | Values |
|---|---|
| `scope` | `branch` (default) or `company` |
| `branch_id` | required when `scope=branch` |
| `grain` | `day` or `month` |
| `from`, `to` | inclusive. `YYYY-MM-DD` for `grain=day`, `YYYY-MM` for `grain=month` |

```json
{
  "results": [
    {"period": "2026-11-26", "branch_id": "BR-04", "revenue": "1240.50", "units": 412, "orders": 131, "avg_basket": "9.47", "status": "PROVISIONAL"},
    {"period": "2026-11-25", "branch_id": "BR-04", "revenue": "1188.10", "units": 397, "orders": 126, "avg_basket": "9.43", "status": "PROVISIONAL"}
  ],
  "count": 2
}
```

Revenue and units are net of refunds, counted on the refund day. `orders` counts the distinct orders sold in the period, refunded or not, so a refund lowers revenue and leaves `orders` alone. It is always counted from `fact_sales_line`, never summed from `agg_sales_daily.order_count`, which counts orders per SKU. `avg_basket` is `revenue / orders`, or `"0.00"` with no orders. With `scope=company`, `branch_id` is `ALL` and the numbers are the sum of every branch, so they always match the branch reports.

Built in Phase 3: `scope=branch` with `grain=day`. Anything else returns 400 `VALIDATION_ERROR` until Phase 4.

- `from` and `to` default to today. A range is at most 366 days and is not paginated.
- Rows come newest first. Today is read live from the facts and always has a row when it is in the range, with zeros before the first sale. A past day has a row once `day_close` (J2) has written its `agg_sales_daily` rows.

### `GET /reports/branches/compare?month=YYYY-MM`

One row per branch for the month (design doc §9.1).

```json
{
  "results": [
    {"branch_id": "BR-01", "name": "Riverside", "revenue": "41230.80", "units": 13890, "orders": 4410, "avg_basket": "9.35",
     "growth_vs_last_year": null, "stockout_days": 3, "status": "FINAL"}
  ],
  "count": 5
}
```

`growth_vs_last_year` is a decimal string such as `"0.082"` (8.2%), or `null` when there is no data for the same month last year. The seeded history has only 6 months, so it is `null` in the demo. `stockout_days` counts branch, SKU and day rows with a stockout.

### `GET /reports/top-skus?branch_id=&from=&to=&limit=10`

The best sellers by revenue in the date range. Omit `branch_id` for the company (HQ only).

```json
{"results": [{"sku": "COKE-330", "name": "Coca-Cola 330 ml", "category_name": "Beverages", "units": 820, "revenue": "574.00"}], "count": 10}
```

## Forecasts

### `GET /forecasts?branch_id=&sku=`

The latest successful forecast run for one branch and SKU, with the last 56 days of actuals for the chart.

```json
{
  "branch_id": "BR-04", "sku": "COKE-330",
  "run": {"run_id": "7a2d…", "method": "HOLT_WINTERS", "data_cutoff": "2026-11-27", "wape": "0.1840", "baseline_wape": "0.2610"},
  "actuals": [{"date": "2026-11-27", "units": 14}],
  "forecast": [{"target_date": "2026-11-28", "units_low": "9.10", "units_mid": "13.40", "units_high": "17.70"}]
}
```

`method` is `HOLT_WINTERS`, `WEEKDAY_AVG` or `FALLBACK`. `wape` scores the previous run against actuals. `baseline_wape` is the "same weekday last week" baseline the chart shows next to it (design doc §9.2). The band is 80%.

## Recommendations

### `GET /recommendations?branch_id=&status=PENDING`

`status` defaults to `PENDING`. Other values are `APPROVED`, `EDITED`, `REJECTED` and `EXPIRED`.

```json
{
  "results": [
    {"recommendation_id": "c0a1…", "run_id": "7a2d…", "branch_id": "BR-04", "sku": "COKE-330", "name": "Coca-Cola 330 ml",
     "type": "REORDER", "suggested_qty": 48, "supplier_id": "5f3b…", "source_branch_id": null,
     "reason": "14d demand 42, safety 9, on hand 6, on order 0, pack 24", "status": "PENDING", "fallback": false}
  ],
  "count": 12
}
```

`type` is `REORDER` (with `supplier_id`) or `TRANSFER` (with `source_branch_id`). Transfers are deferred, so the demo shows only reorders. `fallback` is true when the forecast failed and the 28-day average was used instead (design doc §11.2).

### `POST /recommendations/{id}/decision`

```json
{"outcome": "EDITED", "final_qty": 36, "note": "Promo ends Friday"}
```

`outcome` is `APPROVED`, `EDITED` or `REJECTED`. `final_qty` is required for `EDITED` and defaults to `suggested_qty` for `APPROVED`. Returns 201:

```json
{"recommendation_id": "c0a1…", "outcome": "EDITED", "final_qty": 36, "note": "Promo ends Friday",
 "decided_by": "4c1e…", "decided_at": "2026-11-28T08:41:10+07:00"}
```

`APPROVED` and `EDITED` publish `replenishment.approved` in the same transaction, and Inventory creates the purchase order. A recommendation that is no longer `PENDING` returns 409 `ALREADY_DECIDED`.

### `POST /recommendations/{id}/explain`

Returns the stored "Why?" explanation. If there isn't one yet, it calls the LLM first, which can take up to a minute. If the LLM fails, the recommendation's `reason` is returned with `status` `FALLBACK`.

```json
{"recommendation_id": "c0a1…", "text": "BR-04 is expected to sell about 42 cans over the next 14 days…",
 "status": "OK", "model": "gemma4:12b", "created_at": "2026-11-28T00:41:55+07:00"}
```

## Briefings

### `GET /briefings?branch_id=&date=`

The morning briefing for a branch, or for the company with `branch_id=ALL` (HQ only). `date` defaults to today. Returns 404 `NOT_FOUND` if J7 has not run for that day.

```json
{
  "briefing_id": "e19c…", "branch_id": "BR-04", "briefing_date": "2026-11-28",
  "status": "OK", "model": "gemma4:12b", "prompt_version": "briefing-v1",
  "output": {"headline": "…", "highlights": ["…", "…", "…"], "risks": ["…"], "actions": ["…"]},
  "created_at": "2026-11-28T00:42:30+07:00"
}
```

With `status` `FALLBACK`, `model` is `TEMPLATE` and the card shows "Automatic summary".

## Stock policies

### `GET /stock-policies?branch_id=`

```json
{"results": [{"branch_id": "BR-04", "category_id": "9d2e…", "category_name": "Beverages", "service_level": "0.950", "review_days": 1}], "count": 10}
```

### `PUT /stock-policies`

Creates or replaces the policy for one branch and category. Returns the saved row. `service_level` must be between 0 and 1.

```json
{"branch_id": "BR-04", "category_id": "9d2e…", "service_level": "0.975", "review_days": 2}
```

## Deferred: anomalies

`GET /anomalies?branch_id=&status=OPEN` lists SKUs that sold below `units_low` two days in a row. `PATCH /anomalies/{id}` with `{"status": "CHECKED"}` or `{"status": "DISMISSED"}` closes one. The `sales_anomaly` table exists. J4 and these endpoints are built only if time allows.

## Events

| | Topics |
|---|---|
| Consumes | `branch.upserted`, `product.upserted`, `supplier_terms.changed`, `order.completed`, `order.refunded`, `stock.adjusted` |
| Publishes | `replenishment.approved` |

Handlers in Phase 2:

- `branch.upserted` upserts `dim_branch`, and `product.upserted` upserts `dim_product`.
- `supplier_terms.changed` keeps one `supplier_terms` row per SKU, for the preferred supplier only. An event with `is_preferred: false` deletes the row only if it still belongs to that supplier. An event with `is_preferred: true` is ignored if the row was written by a newer event. So a supplier swap ends with the new supplier, whatever order the two suppliers' events arrive in.

`calendar` holds every day from 2025-01-01 to 2027-12-31 (`weekday` is ISO, Monday = 1). `is_holiday` is false everywhere for now.

Handlers in Phase 3:

- `order.completed` inserts one `SALE` row per line into `fact_sales_line`, and `order.refunded` one `REFUND` row per line with negative `qty` and `net_amount`, dated `refund_date`. Both use `ON CONFLICT DO NOTHING` on `(order_id, line_no, entry_type)` and mark `(branch_id, sale_date)` in `dirty_day`.
- `stock.adjusted` upserts `stock_current` only when the event's `version` is newer than the stored one.

Jobs in Phase 3:

- `day_close` (J2) recomputes `agg_sales_daily` for every day in `dirty_day` and for yesterday, clears those markers in the same transaction, writes yesterday's `fact_stock_daily` from `stock_current`, and marks days more than 3 days old `FINAL`. It then recomputes `agg_sales_monthly` for the months those days fall in.
- `month_close` (J6) recomputes `agg_sales_monthly` for every month that has daily rows. A month is `FINAL` when it has ended and all its days are final.

`scripts/fake_orders.py` publishes test `order.completed` events.
