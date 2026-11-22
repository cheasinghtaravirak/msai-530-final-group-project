# Reduced-scope architecture

The full target architecture lives in the Claude artifact linked from [`../artifact.md`](../artifact.md): 8 services, Kafka, ClickHouse, Airflow, Keycloak, MLflow and 3 client apps. That design is right for a real retailer, but it is too big for a 4-person team that must deliver a **working web app**.

This folder describes two buildable scopes. Both keep the ideas the course is testing (a database per service, events, idempotent consumers, a reporting pipeline and forecasting) while cutting the infrastructure and the number of front ends.

| Document | Scope |
|---|---|
| [option-a-staff-app.md](option-a-staff-app.md) | **Option A.** One web app for staff only (HQ admin, branch manager, cashier). Every sale happens at the POS. |
| [option-b-staff-app-plus-storefront.md](option-b-staff-app-plus-storefront.md) | **Option B.** Option A plus a customer storefront for online click-and-collect orders. Written as changes on top of Option A. |

## What changes from the full design

| Full design | Reduced scope (A and B) | Why |
|---|---|---|
| 3 client apps | 1 web app with role-based screens (B adds public `/shop` routes in the same app) | One codebase, one login, one deploy |
| 8 services | 5 services: Admin, Catalog, Inventory, Order, Analytics | Merge services that the same person would own anyway |
| Identity (Keycloak) + Branch | **Admin** service issuing its own JWTs | Keycloak setup costs more than it teaches here |
| Reporting + Forecasting + Replenishment | **Analytics** service with 3 internal modules | Same data, same nightly schedule, one owner |
| Kafka + schema registry | Kafka, single broker in KRaft mode, JSON events with a versioned envelope, no schema registry | Keeps the retained log (replay, late consumers, cache rebuilds); a registry adds little at this size |
| ClickHouse + S3 + MLflow | PostgreSQL `analytics_db` | Data volume is small; SQL is enough |
| (not in full design) | Local LLM via Ollama writes manager briefings and recommendation explanations (Option A, section 9.4) | Visible generative AI; it only narrates computed numbers, with a template fallback |
| Airflow | APScheduler inside Analytics, plus "Run now" endpoints | A few nightly jobs run in sequence; no separate scheduler needed |
| ML model with weekly retrain | Statistical forecast (weekday average or Holt-Winters) | Explainable, no training pipeline |
| Branch-local timezones | Single timezone (`Asia/Phnom_Penh`), column kept for later | Removes a whole class of day-boundary bugs |
| POS offline queue | Not built; client-generated `order_id` still makes retries safe | Hard in a browser; out of scope |

## Fixes carried in from the design review

Both options also fix the issues found when reviewing the full design:

- **One sale recognition point.** POS sales count at `order.completed`, online sales at `order.paid`. A sale never moves between days.
- **Late data.** A "dirty day" marker replaces the fixed 3-day window, so a late event of any age gets re-aggregated. A nightly check against Order's totals catches missing events.
- **Every event carries `channel`.** Consumers can tell POS from online.
- **`region` exists on `branch`.**
- **Each job writes only its own service's tables.** Replenishment decisions are no longer exported into another service's schema; they live in the same Analytics database.
- **One preferred supplier per SKU**, and Inventory owns purchase orders, so an approved reorder becomes a real document.
- **Event fields are spelled out** in every communication matrix row.
- **A failure-handling section** answers the "defend your design" questions directly.

## Comparison

| | Option A | Option B |
|---|---|---|
| Front-end areas | 3 role areas (HQ, manager, cashier) | 3 role areas + public storefront + customer account |
| Order flow | One request: sale is created already completed | Saga: pending → reserved → paid → ready → completed |
| Inventory | Ledger, receipts, transfers, purchase orders | All of A + reservations with expiry |
| Events | 8 | 13 |
| Relative effort | Baseline | About 35–50% more, mostly Order, Inventory and the front end |
| Demo story | "A day in the life of a branch, then HQ reviews reports and approves reorders" | Same, plus "a customer orders online and collects in store" |
| Main risk | Low | The reservation saga is the hardest part to get right |

**Recommendation:** build Option A first, with every interface Option B needs left open (the `channel` field, the `CUSTOMER` role code, order statuses as an enum). Add Option B only if A is finished and tested with time left. Option B's document lists exactly what to add.

**Decision (2026-11-22): the team builds Option A.** Its document was then revised after an architecture review: Kafka instead of RabbitMQ, APScheduler instead of Celery, plus a demo priority list and a timeline (see its section 14). Option B is deferred. Its document still describes RabbitMQ queues; if it is ever built, each queue becomes a Kafka consumer group on the same events.

## Confirm with the lecturer

1. Is a customer-facing app required, or is POS-only ordering acceptable? (This decides A vs B.)
2. Must the backend run as separate deployable services, or is a modular monolith acceptable? (Both options assume separate services.)
3. Is the full artifact accepted as the "target architecture" with this build as phase 1?

## Shared assumptions

- One company (`shop`), about 5–20 branches, one country, one currency (USD).
- Payments at the POS are recorded, not processed. Cash, card and QR are just a `method` value.
- Tax and discounts are out of scope. `total = sum(line_total)`.
- Refunds are whole-order only.
- The stack is Django + DRF services, a React front end, PostgreSQL, Kafka, APScheduler, and Ollama on the host for the LLM.
