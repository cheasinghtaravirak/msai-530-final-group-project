#!/usr/bin/env bash
# Generate Django migrations for a service, using its Docker image (no local Python setup needed).
#
#   scripts/makemigrations.sh <service> [app ...]
#   scripts/makemigrations.sh inventory stock purchasing
#   scripts/makemigrations.sh admin retail_common      # migrations for the shared library
#
# The repo is mounted into the container, so the new files land in your working tree.
# Rebuild afterwards:  docker compose up -d --build <service> <service>-worker
set -euo pipefail

svc="${1:?usage: scripts/makemigrations.sh <service> [app ...]}"
shift

cd "$(dirname "$0")/.."
src="$(pwd -W 2>/dev/null || pwd)"   # pwd -W gives a Windows path under Git Bash

docker compose build "$svc" >/dev/null
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$src:/src" \
  -w "/src/services/$svc" \
  -e PYTHONPATH=/src/libs/retail_common \
  -e SERVICE_NAME="$svc" \
  -e DATABASE_URL=postgres://unused:unused@unused/unused \
  "retail/$svc" \
  python manage.py makemigrations "$@" 2> >(grep -v "consistent migration history\|warnings.warn" >&2)
