#!/usr/bin/env python3
"""Tests for project acceptance and revision reflection."""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from ade.core.config import get_config
from ade.ui.main import app


def test_accept_project() -> None:
    config = get_config()
    client = TestClient(app)
    client.post(
        "/auth/login",
        data={"username": config.admin_username, "password": config.admin_password},
        follow_redirects=True,
    )
    project_id = "test-bootstrap-001"
    res = client.post(f"/api/projects/{project_id}/accept")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["acceptance_status"] == "accepted"

    project = client.get(f"/api/projects/{project_id}").json()
    assert project["acceptance_status"] == "accepted"
    print("[OK] Project accept")


def test_accept_idempotent_ui_state() -> None:
    config = get_config()
    client = TestClient(app)
    client.post(
        "/auth/login",
        data={"username": config.admin_username, "password": config.admin_password},
        follow_redirects=True,
    )
    project_id = "test-bootstrap-001"
    client.post(f"/api/projects/{project_id}/accept")
    res = client.post(f"/api/projects/{project_id}/accept")
    assert res.json()["status"] == "ok"
    print("[OK] Accept idempotent")


def main() -> int:
    print("=== ADE v4 Reflection Test ===\n")
    try:
        test_accept_project()
        test_accept_idempotent_ui_state()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    print("\n=== All reflection checks passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())