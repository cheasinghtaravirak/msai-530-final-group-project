#!/bin/sh
# Runs once, when the postgres volume is first created.
# One database and one login per service. CONNECT is revoked from PUBLIC,
# so a service's user can only connect to its own database (design doc §5.6).
set -eu

for svc in admin catalog inventory order analytics; do
  pw_var=$(echo "${svc}_DB_PASSWORD" | tr '[:lower:]' '[:upper:]')
  eval "pw=\${$pw_var}"

  echo "Creating ${svc}_db and ${svc}_svc"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE USER ${svc}_svc WITH PASSWORD '${pw}';
CREATE DATABASE ${svc}_db OWNER ${svc}_svc;
REVOKE CONNECT ON DATABASE ${svc}_db FROM PUBLIC;
GRANT CONNECT ON DATABASE ${svc}_db TO ${svc}_svc;
SQL
done

# Service users should not use the default databases either.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;
SQL
