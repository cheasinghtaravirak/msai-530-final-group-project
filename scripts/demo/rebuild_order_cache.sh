#!/usr/bin/env bash
# Wipe Order's product and price caches and rebuild them from the compacted topics.
set -euo pipefail
cd "$(dirname "$0")/../.."

sql() { docker compose exec -T postgres psql -U postgres -d "$1" -tAc "$2"; }
counts() {
  echo "$(sql order_db 'select count(*) from product_cache') products, $(sql order_db 'select count(*) from price_cache') prices"
}

catalog="$(sql catalog_db 'select count(*) from sku') products, $(sql catalog_db 'select count(*) from price') prices"
echo "catalog:      $catalog"
echo "order before: $(counts)"

docker compose stop order-worker
docker compose exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 --delete --group order
sql order_db "TRUNCATE product_cache, price_cache, branch_ref" >/dev/null
forget_replayed_events() {
  sql order_db "DELETE FROM processed_event WHERE event_type IN ('product.upserted', 'price.changed', 'branch.upserted')" >/dev/null
}
forget_replayed_events
echo "order wiped:  $(counts)"

docker compose start order-worker
start=$SECONDS
until [ "$(counts)" = "$catalog" ]; do
  if (( SECONDS - start > 120 )); then echo "order after 120 s: $(counts)" >&2; exit 1; fi
  sleep 1
done
echo "order after $((SECONDS - start)) s: $(counts)"
