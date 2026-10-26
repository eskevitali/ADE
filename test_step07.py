#!/usr/bin/env python3
"""Step 07: Deployer, workspace status, PostgreSQL event store."""

from __future__ import annotations

import sys
import uuid

import pytest

from fastapi.testclient import TestClient

from ade.core.adi_manager import ADIManager
from ade.core.config import get_config
from ade.core.deployer import DeployerService
from ade.memory.event_store import EventStore
from ade.ui.main import app


def _login(client: TestClient) -> None:
    config = get_config()
    client.post(
        "/auth/login",
        data={"username": config.admin_username, "password": config.admin_password},
        follow_redirects=True,
    )


def test_event_store_schema() -> None:
    store = EventStore()
    if not store.is_available():
        print("[SKIP] PostgreSQL not available")
        return
    store.ensure_schema()
    pid = f"test-events-{uuid.uuid4().hex[:8]}"
    eid = store.record(pid, "test_event", data={"ok": True}, actor="test")
    assert eid is not None
    events = store.list_events(pid, limit=5)
    assert events and events[0]["event_type"] == "test_event"
    print("[OK] Event store record + list")


@pytest.mark.docker
def test_deploy_workspace() -> None:
    adi = ADIManager()
    deployer = DeployerService(adi_manager=adi)
    temp_id = f"test-deploy-{uuid.uuid4().hex[:8]}"
    adi.bootstrap(temp_id, "Deploy Test", "web static test")
    adi.write_spec(temp_id, "# Static site\nDisplay a heading")
    src = adi.project_path(temp_id) / "src"
    src.mkdir(exist_ok=True)
    (src / "index.html").write_text("<html><body><h1>ADE Deploy OK</h1></body></html>", encoding="utf-8")

    result = deployer.deploy(temp_id, use_agent=False)
    assert result.get("status") == "ok", result
    status = deployer.get_workspace_status(temp_id)
    ws = status.get("workspace", {})
    assert ws.get("state") in ("running", "created", "restarting"), ws
    print(f"[OK] Deploy workspace state={ws.get('state')} port={ws.get('host_port')}")

    adi.teardown(temp_id)
    import shutil
    shutil.rmtree(adi.project_path(temp_id), ignore_errors=True)


def test_compose_python_script_mode() -> None:
    adi = ADIManager()
    deployer = DeployerService(adi_manager=adi)
    temp_id = f"test-script-{uuid.uuid4().hex[:8]}"
    adi.bootstrap(temp_id, "Script Deploy", "cli script")
    src = adi.project_path(temp_id) / "src"
    (src / "main.py").write_text("print('script ok')\n", encoding="utf-8")
    compose_path = deployer._ensure_compose(temp_id, "Script Deploy")
    content = compose_path.read_text(encoding="utf-8")
    assert len(content) > 100, "compose must not be empty for python_script mode"
    assert "python_script" in content or "python src/main.py" in content
    print("[OK] python_script compose file is non-empty")

    adi.teardown(temp_id)
    import shutil
    shutil.rmtree(adi.project_path(temp_id), ignore_errors=True)


@pytest.mark.docker
def test_deploy_api() -> None:
    adi = ADIManager()
    temp_id = f"test-deploy-api-{uuid.uuid4().hex[:8]}"
    adi.bootstrap(temp_id, "API Deploy", "api test")
    adi.write_spec(temp_id, "# Static site\nDisplay a heading")
    (adi.project_path(temp_id) / "src").mkdir(exist_ok=True)
    (adi.project_path(temp_id) / "src" / "index.html").write_text("<h1>api</h1>", encoding="utf-8")

    client = TestClient(app)
    _login(client)
    res = client.post(f"/api/projects/{temp_id}/deploy")
    data = res.json()
    assert data.get("status") == "ok", data
    st = client.get(f"/api/projects/{temp_id}/status").json()
    assert st.get("status") == "ok"
    assert "workspace" in st
    print("[OK] POST deploy + GET status API")

    adi.teardown(temp_id)
    import shutil
    shutil.rmtree(adi.project_path(temp_id), ignore_errors=True)


def main() -> int:
    print("=== Step 07 tests ===\n")
    try:
        test_event_store_schema()
        test_deploy_workspace()
        test_compose_python_script_mode()
        test_deploy_api()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    print("\n=== Step 07 passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())