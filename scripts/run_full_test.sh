#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --frozen --extra dev
uv run --no-sync ruff check ade tests conftest.py
uv run --no-sync pytest -q "$@"
