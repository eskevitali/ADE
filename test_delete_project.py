#!/usr/bin/env python3
"""Tests for project delete — real Я тут / V2 are never removed."""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from ade.core.adi_manager import ADIManager
from ade.core.config import get_config
from ade.ui.main import app

YATUT_ID = "658fbae8-5606-42f6-858a-5b2cdd0d33be"
YATUT_V2_ID = "203941da-7cd3-430d-b26a-f8bf9fe3b178"


def _login(client: TestClient) -> None:
    config = get_config()
    client.post(
        "/auth/login",
        data={"username": config.admin_username, "password": config.admin_password},
        follow_redirects=True,
    )


def _assert_preserved(adi: ADIManager) -> None:
    for pid in (YATUT_ID, YATUT_V2_ID):
        assert adi.get_project(pid) is not None, f"Project {pid} must not be deleted"
        assert (adi.project_path(pid) / "manifest.json").exists()
    print(f"[OK] Preserved: Я тут + Я тут V2")


def test_eligibility_yatut_projects() -> None:
    client = TestClient(app)
    _login(client)
    for pid in (YATUT_ID, YATUT_V2_ID):
        res = client.get(f"/api/projects/{pid}/delete-eligibility")
        data = res.json()
        assert data["status"] == "ok", data
        assert data["can_delete"] is True, data
    print("[OK] Delete eligibility for Я тут and V2")


def test_confirm_name_mismatch() -> None:
    client = TestClient(app)
    _login(client)
    res = client.request(
        "DELETE",
        f"/api/projects/{YATUT_ID}",
        json={"confirm_name": "wrong name"},
    )
    assert res.json()["message"] == "confirm_name_mismatch"
    print("[OK] Confirm name mismatch blocks delete")


def test_delete_disposable_clone() -> None:
    adi = ADIManager()
    config = get_config()
    temp_id = f"test-delete-{uuid.uuid4().hex[:8]}"
    adi.bootstrap(temp_id, "Disposable Delete Test", "temp project for delete test")
    (adi.project_path(temp_id) / "spec").mkdir(exist_ok=True)
    assert adi.get_project(temp_id) is not None

    client = TestClient(app)
    _login(client)
    res = client.request(
        "DELETE",
        f"/api/projects/{temp_id}",
        json={"confirm_name": "Disposable Delete Test"},
    )
    data = res.json()
    assert data["status"] == "ok", data
    assert not adi.project_path(temp_id).exists()
    print(f"[OK] Deleted disposable project {temp_id}")


def test_block_pending_revision() -> None:
    adi = ADIManager()
    temp_id = f"test-delete-block-{uuid.uuid4().hex[:8]}"
    adi.bootstrap(temp_id, "Block Test", "block delete test")
    manifest = adi._read_manifest(temp_id)
    manifest["pending_revision_id"] = 1
    adi._write_manifest(temp_id, manifest)

    block = adi.get_delete_block_reason(temp_id)
    assert block == "pending_revision_review"
    result = adi.delete_project(temp_id)
    assert result["message"] == "pending_revision_review"
    shutil.rmtree(adi.project_path(temp_id), ignore_errors=True)
    print("[OK] Block delete when pending revision")


def main() -> int:
    print("=== Delete project tests (Я тут / V2 preserved) ===\n")
    adi = ADIManager()
    try:
        test_eligibility_yatut_projects()
        test_confirm_name_mismatch()
        test_delete_disposable_clone()
        test_block_pending_revision()
        _assert_preserved(adi)
    except Exception as exc:
        _assert_preserved(adi)
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    print("\n=== All delete tests passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())