#!/usr/bin/env bash
set -euo pipefail

# The same image runs under Compose (port 8000) and on Cloud Run, which sets PORT
# (8080) and sends plain HTTP to it. No Lambda adapter is involved.
PORT="${PORT:-8000}"

# alembic upgrade head is idempotent. Set MIGRATE_ON_START=false to skip it when
# something else owns schema changes.
if [[ "${MIGRATE_ON_START:-true}" == true ]]; then
  echo "[entrypoint] applying migrations..."
  alembic upgrade head
fi

echo "[entrypoint] starting uvicorn on port ${PORT}..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --proxy-headers \
  --forwarded-allow-ips '*' \
  --log-level "${LOG_LEVEL:-info}"
