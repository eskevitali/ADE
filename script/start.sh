#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== ADE v4 Startup ==="

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "WARNING: .env not found, copying from .env.example"
  cp .env.example .env
fi

echo "[1/4] Building images..."
docker compose build

echo "[2/4] Starting services (host network)..."
docker compose up -d

echo "[3/4] Waiting for backend health..."
for i in $(seq 1 40); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "Backend is healthy."
    break
  fi
  if [[ "$i" -eq 40 ]]; then
    echo "ERROR: backend did not become healthy in time" >&2
    docker compose logs backend --tail 30
    exit 1
  fi
  sleep 2
done

echo "[4/4] Service status:"
docker compose ps

HEALTH=$(curl -s http://127.0.0.1:8000/health)
DASH_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/dashboard)

echo ""
echo "Health:  ${HEALTH}"
echo "Dashboard HTTP code: ${DASH_CODE}"
echo ""
echo "=== ADE v4 is running ==="
echo "  Local:     http://127.0.0.1:8000/dashboard"
echo "  Public:    https://ade.kider.at/dashboard  (NPM → ade-v4-backend-1:8000)"
echo "  API docs:  https://ade.kider.at/docs"
echo "  WebSocket: wss://ade.kider.at/ws"
echo ""
echo "Full test: ./scripts/run_full_test.sh"