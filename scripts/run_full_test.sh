#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source "${HOME}/.local/bin/env" 2>/dev/null || true

echo "=== ADE v4 Full Test Suite ==="
uv sync --quiet
uv run python test_orchestrator.py
uv run python test_workflow_e2e.py
uv run python test_bootstrap.py
uv run python test_auth.py
uv run python test_spec_parser.py
uv run python test_reflection.py
uv run python test_revision_diff.py
uv run python test_revision_flow.py
uv run python test_delete_project.py
uv run python test_step07.py
echo ""
echo "=== Full test suite passed ==="
