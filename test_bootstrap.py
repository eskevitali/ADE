#!/usr/bin/env python3
"""Tests for ADI bootstrap, isolation, and human-in-the-loop."""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

from ade.core.adi_manager import ADIManager, extract_code_blocks
from ade.core.approval_gate import ApprovalGate, GateStatus
from ade.core.config import get_config
from ade.workflows.bootstrap_cycle import BootstrapCycleOrchestrator


def test_extract_code_blocks() -> None:
    content = """Here is code:
```python main.py
def hello():
    return "hi"
```
"""
    blocks = extract_code_blocks(content)
    assert len(blocks) == 1
    assert blocks[0][0] == "main.py"
    assert "def hello" in blocks[0][1]
    print("[OK] Code block extraction")


def test_adi_bootstrap() -> None:
    config = get_config()
    manager = ADIManager()
    project_id = "test-bootstrap-001"
    project = manager.bootstrap(
        project_id,
        "Test Project",
        "A simple hello world API",
        enable_isolation=False,
    )
    path = Path(project.path)
    assert path.exists()
    assert (path / "manifest.json").exists()
    assert (path / "docker-compose.yml").exists()
    assert (path / "src").is_dir()

    manager.write_spec(project_id, "# Spec\nDetails here")
    manager.write_code(project_id, "print('hello')")
    manager.write_review(project_id, "Looks good")

    assert (path / "spec" / "SPEC.md").read_text(encoding="utf-8").startswith("# Spec")
    assert (path / "src" / "main.py").exists()
    assert (path / "review" / "REVIEW.md").exists()

    loaded = manager.get_project(project_id)
    assert loaded is not None
    assert loaded.status == "completed"
    projects = manager.list_projects()
    assert any(p.id == project_id for p in projects)
    print(f"[OK] ADI bootstrap: {path.relative_to(config.root_dir)}")


def test_approval_gate() -> None:
    gate = ApprovalGate()
    task_id = "task-123"

    def waiter() -> GateStatus:
        gate.open(task_id, "spec")
        return gate.wait(task_id, "spec", timeout=2.0)

    thread = threading.Thread(target=waiter)
    thread.start()
    time.sleep(0.1)
    assert gate.approve(task_id, "spec")
    thread.join(timeout=3)
    assert not thread.is_alive()
    state = gate.get_state(task_id, "spec")
    assert state is not None
    assert state.status == GateStatus.APPROVED
    print("[OK] Approval gate")


def test_bootstrap_cycle_without_llm() -> None:
    """Compile/import check only — full run needs API keys."""
    from fastapi.testclient import TestClient

    from ade.core.config import get_config
    from ade.ui.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/projects" in paths
    assert "/api/tasks/{task_id}/approve" in paths

    config = get_config()
    client = TestClient(app)
    client.post(
        "/auth/login",
        data={"username": config.admin_username, "password": config.admin_password},
        follow_redirects=True,
    )
    assert client.get("/api/projects").status_code == 200
    page = client.get("/projects/test-bootstrap-001")
    assert page.status_code == 200
    assert "Test Project" in page.text
    print("[OK] Bootstrap API routes and project page")


def test_bootstrap_cycle_run() -> None:
    config = get_config()
    if not config.has_openrouter() and not config.has_xai():
        print("[SKIP] Bootstrap cycle run: no API keys")
        return

    manager = ADIManager()
    project_id = "test-hitl-001"
    task_id = "task-hitl-001"
    manager.bootstrap(project_id, "HITL Test", "Say hello", enable_isolation=False)

    events: list[str] = []

    def on_event(name: str, _data: dict) -> None:
        events.append(name)
        if name == "awaiting_approval" and _data.get("gate") == "spec":
            gate = ApprovalGate()
            gate.approve(task_id, "spec")

    gate = ApprovalGate()

    def on_event_with_approve(name: str, data: dict) -> None:
        events.append(name)
        if name == "awaiting_approval":
            gate_name = data.get("gate", "")
            gate.approve(task_id, gate_name)

    orch = BootstrapCycleOrchestrator(
        task_id=task_id,
        project_id=project_id,
        adi_manager=manager,
        gate=gate,
        human_in_loop=True,
        on_event=on_event_with_approve,
    )
    result = orch.run("Create a one-line Python hello function.")
    assert result.get("spec") or result.get("review")
    assert "awaiting_approval" in events
    manifest = json.loads(
        (manager.project_path(project_id) / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] in ("code_ready", "completed")
    print(f"[OK] Bootstrap cycle run: status={result.get('status')}")


def main() -> int:
    print("=== ADE v4 Bootstrap Test ===\n")
    try:
        test_extract_code_blocks()
        test_adi_bootstrap()
        test_approval_gate()
        test_bootstrap_cycle_without_llm()
        test_bootstrap_cycle_run()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    print("\n=== All bootstrap checks passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())