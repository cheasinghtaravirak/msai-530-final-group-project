# Multi-Branch Shop Order Management System

Advanced Programming group project: a microservices redesign of a multi-branch retail system, with reporting, forecasting and an LLM assistant.

- **Design:** [docs/reduced-scope/option-a-staff-app.md](docs/reduced-scope/option-a-staff-app.md)
- **Plan and task list:** [docs/implementation-plan.md](docs/implementation-plan.md)
- **Brief:** [docs/instruction.md](docs/instruction.md)

## Run it

You need Docker Desktop (give it at least 8 GB of memory) and Python 3 for one setup script.

```bash
pip install cryptography
python scripts/gen_env.py        # once: creates .env with secrets and JWT keys
docker compose up -d --build     # first build takes a few minutes
```

| URL | What |
|---|---|
| http://localhost:8080 | Web app and APIs (`/api/<service>/...`) |
| http://localhost:8081 | Kafka UI: topics, messages, consumer lag, DLQs |

Log in as `hq@demo.local` / `demo1234` (HQ admin, created on first start).

Check that everything is up:

```bash
docker compose ps                                   # kafka-init "Exited (0)" is expected
curl http://localhost:8080/api/analytics/health
```

## What's running

| Container | Role |
|---|---|
| `gateway` | Nginx: `/` → web, `/api/<service>/<path>` → `<service>:8000/<path>` |
| `web` | React app (Vite + Mantine), built and served by Nginx |
| `admin`, `catalog`, `inventory`, `order`, `analytics` | Django REST services, one database each |
| `*-relay`, `*-worker` | Outbox relay (publishes events) + Kafka consumer, same image as the service |
| `analytics-scheduler` | APScheduler: nightly jobs and "Run now" requests. Exactly one instance. |
| `postgres` | One server, 5 databases, 5 users; each user can only connect to its own database |
| `kafka` | Single broker, KRaft mode. Topics are created by `kafka-init` from `libs/retail_common/retail_common/topics.py` |
| `kafka-ui` | Kafka web UI |

Ollama is **not** in Docker: it runs on the host. Analytics calls it at `OLLAMA_URL` (default `http://host.docker.internal:11434`, model `gemma4:12b`). Without Ollama, set `LLM_PROVIDER=fake` in `.env`.

## Repository layout

```
infra/                 postgres init, gateway config
libs/retail_common/    shared library: auth, outbox, Kafka consumer, topics, error format
services/<name>/       one Django project per service (config/ + apps)
services/Dockerfile    one image recipe for all services
web/                   React front end
scripts/               gen_env.py, makemigrations.sh, smoke tests, demo helpers
docs/                  design, plan, brief
```

## Developing a service

**Publish an event.** Call it in the same transaction as the change; the relay sends it to Kafka:

```python
from django.db import transaction
from retail_common.events import publish_event

with transaction.atomic():
    order = Order.objects.create(...)
    publish_event("order.completed", payload, key=str(order.order_id))
```

**Consume an event.** Register a handler in `<app>/handlers.py` and list the module in `EVENT_HANDLER_MODULES` in the service's `config/settings.py`. The handler runs once per event, inside a transaction:

```python
from retail_common.consumer import handles

@handles("order.completed")
def on_order_completed(event):
    p = event["payload"]
    ...
```

**Protect an endpoint:**

```python
from retail_common.auth import HQ_ADMIN, BRANCH_MANAGER, HasRole

class StockView(APIView):
    permission_classes = [HasRole(HQ_ADMIN, BRANCH_MANAGER, branch_from="branch_id")]
```

**Return a business error:** `raise ApiError("PRICE_UNAVAILABLE", "No price for COKE-330", status=422)`.

**After changing models:**

```bash
scripts/makemigrations.sh inventory stock          # writes the migration into your working tree
docker compose up -d --build inventory inventory-worker
```

**Front end:** `cd web && npm install && npm run dev` gives you hot reload at http://localhost:5173 (it proxies `/api` to the gateway on 8080, so keep the stack running).

## Useful commands

```bash
docker compose logs -f inventory-worker                     # follow a service's logs
docker compose up -d --build order order-worker             # rebuild after code changes
docker compose exec postgres psql -U postgres -d order_db   # look at a database
docker compose down -v                                      # stop and DELETE all data
```

Under Git Bash, prefix commands that pass container paths with `MSYS_NO_PATHCONV=1`, e.g.
`MSYS_NO_PATHCONV=1 docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list`.

## Troubleshooting

- **"ports are not available"** on Windows: Hyper-V reserves some port ranges. Check with `netsh interface ipv4 show excludedportrange protocol=tcp` and change the host port in `docker-compose.yml`.
- **Services restart in a loop after changing `.env` passwords:** passwords only apply when the postgres volume is created. Run `docker compose down -v`.
- **A consumer isn't getting events:** check `kafka-ui` → Consumers for lag, and `<topic>.dlq` for messages that failed 3 times.
