#!/usr/bin/env python3
"""End-to-end test for Dev Cycle workflow and UI integration."""

from __future__ import annotations

import sys

from ade.core.agent_team import AgentTeam
from ade.core.config import get_config
from ade.memory.vector_store import VectorStore
from ade.workflows.dev_cycle import DevCycleOrchestrator, build_dev_cycle


def test_dev_cycle_compile() -> None:
    team = AgentTeam.default()
    graph = build_dev_cycle(team)
    assert graph is not None
    print("[OK] Dev cycle graph compiled")


def test_dev_cycle_events() -> None:
    events: list[str] = []

    def on_event(name: str, data: dict) -> None:
        events.append(name)

    orch = DevCycleOrchestrator(on_event=on_event)
    config = get_config()
    if not config.has_openrouter() and not config.has_xai():
        print("[SKIP] Dev cycle run: no API keys configured")
        return

    result = orch.run("Создай hello-world FastAPI endpoint.")
    assert result["task"]
    assert "workflow_started" in events
    assert "workflow_completed" in events
    assert result.get("spec") or result.get("review")
    print(f"[OK] Dev cycle run: phase={result.get('phase')}, events={len(events)}")


def test_vector_store() -> None:
    store = VectorStore()
    if not store.is_available():
        print("[SKIP] Qdrant not available")
        return
    point_id = store.store_workflow_result(
        task="test task",
        spec="test spec",
        code="print('hi')",
        review="looks good",
        metadata={"test": True},
    )
    assert point_id
    print(f"[OK] Qdrant store: point_id={point_id[:8]}…")


def test_ui_import() -> None:
    from fastapi.testclient import TestClient

    from ade.ui.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/dashboard" in paths
    assert "/projects/new" in paths
    assert "/login" in paths
    assert "/ws" in paths

    client = TestClient(app)
    assert client.get("/dashboard", follow_redirects=False).status_code == 303
    print("[OK] UI routes: dashboard, login, new project, websocket")


def main() -> int:
    print("=== ADE v4 E2E Workflow Test ===\n")
    try:
        test_dev_cycle_compile()
        test_ui_import()
        test_vector_store()
        test_dev_cycle_events()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    print("\n=== All E2E checks passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
