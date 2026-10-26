#!/usr/bin/env bash
set -euo pipefail

HOST="${API_HOST:-0.0.0.0}"
PORT="${API_PORT:-8000}"
QDRANT_URL="${QDRANT_URL:-http://qdrant:6333}"

echo "ADE backend starting on ${HOST}:${PORT}"

for i in $(seq 1 30); do
  if curl -sf "${QDRANT_URL}/healthz" >/dev/null 2>&1; then
    echo "Qdrant is ready at ${QDRANT_URL}"
    break
  fi
  echo "Waiting for Qdrant (${i}/30)..."
  sleep 2
done

exec uv run --no-sync uvicorn ade.ui.main:app --host "${HOST}" --port "${PORT}"