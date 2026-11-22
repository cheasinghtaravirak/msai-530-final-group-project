# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Django microservices (admin, catalog, inventory, order, analytics) + React/Vite web, wired by Kafka, run with Docker Compose. Design: `docs/reduced-scope/option-a-staff-app.md`. Plan and ground rules: `docs/implementation-plan.md`.

## Running and changing code

- First run: `python scripts/gen_env.py` (needs `cryptography`), then `docker compose up -d --build`. Without Ollama on the host, set `LLM_PROVIDER=fake` in `.env`. Never read or commit `.env`.
- Code is baked into images, not mounted. After editing a service, rebuild it and its worker: `docker compose up -d --build order order-worker`. A change in `libs/retail_common` needs a rebuild of every service.
- Migrations: `scripts/makemigrations.sh <service> [app ...]` (shared lib: `scripts/makemigrations.sh admin retail_common`). Don't run `manage.py makemigrations` locally. Migrations apply on container start.
- Tests run inside the service container: `docker compose exec <service> pytest`. pytest-django is not installed yet. Add it to `libs/retail_common/pyproject.toml` when writing the first tests.
- Python lint/format: `ruff check . && ruff format --check .` (config in `ruff.toml`; a project hook runs ruff on every edited `.py` file).
- Web: `npm run typecheck` in `web/`. `npm run dev` (port 5173) proxies `/api` to the gateway, so the stack must be up.
- The gateway port is `${GATEWAY_PORT:-8080}`. `kafka-init` showing "Exited (0)" is normal.

## Cross-service rules

- Each service touches only its own database. No cross-service foreign keys: reference by ID, snapshot values that must not change. Never hard-delete; set `status` to CLOSED or DISCONTINUED instead.
- Publish events only through `retail_common.events.publish_event(...)` inside the same `transaction.atomic()` as the change. The relay sends them to Kafka. Never produce to Kafka directly.
- Every new event type needs an entry in `libs/retail_common/retail_common/topics.py`. Topics are not auto-created.
- Consumers use `@handles("<event>")` in `<app>/handlers.py`, and the module must be listed in `EVENT_HANDLER_MODULES` in the service's `config/settings.py`.
- Errors: `raise ApiError("CODE", "message", status=...)` from `retail_common.api`. Don't return ad-hoc error bodies.
- The gateway strips `/api/<service>`, so service URLs are `/branches`, not `/api/admin/branches`. No trailing slashes (`APPEND_SLASH=False`).
- Money is `DecimalField(12, 2)` and travels as a 2-decimal string in JSON. Never use float.
- Timezone is `Asia/Phnom_Penh`. JSON fields are snake_case.
- Order looks up prices itself and never trusts prices sent by the browser. The LLM only narrates numbers computed by code; it never produces them.
- Service settings start with `from retail_common.settings_base import *  # noqa: F403`.

## Git

- Short branches named like `m3/pos-order-endpoint`. Merge through a PR with one reviewer. `main` must always pass `docker compose up`.
