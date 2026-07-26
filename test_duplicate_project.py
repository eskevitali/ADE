#!/usr/bin/env python3
"""Tests for project duplicate."""

from __future__ import annotations

import json
import sys
import uuid

from fastapi.testclient import TestClient

from ade.core.adi_manager import ADIManager
from ade.core.config import get_config
from ade.ui.main import app


def _login(client: TestClient) -> None:
    config = get_config()
    client.post(
        "/auth/login",
        data={"username": config.admin_username, "password": config.admin_password},
        follow_redirects=True,
    )


def test_suggest_duplicate_name() -> None:
    adi = ADIManager()
    assert adi.suggest_duplicate_name("Я ТУТ") == "Я ТУТ V2"
    assert adi.suggest_duplicate_name("Я ТУТ V2") == "Я ТУТ V3"
    print("[OK] suggest_duplicate_name")


def test_duplicate_project_api() -> None:
    adi = ADIManager()
    source_id = f"test-dup-{uuid.uuid4().hex[:8]}"
    adi.bootstrap(source_id, "Dup Source", "GPS mobile app idea")
    root = adi.project_path(source_id)
    (root / "spec" / "TZ.md").write_text("# TZ\n", encoding="utf-8")
    (root / "spec" / "SPEC.md").write_text("# Spec\n", encoding="utf-8")
    (root / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "preview").mkdir(exist_ok=True)
    (root / "preview" / "mobile-mockup.html").write_text("<html></html>", encoding="utf-8")
    manifest = adi._read_manifest(source_id)
    manifest["status"] = "completed"
    manifest["acceptance_status"] = "accepted"
    manifest["revision_count"] = 2
    adi._write_manifest(source_id, manifest)
    (root / "revisions").mkdir(exist_ok=True)
    (root / "revisions" / "rev-1.json").write_text("{}", encoding="utf-8")

    client = TestClient(app)
    _login(client)
    res = client.post(f"/api/projects/{source_id}/duplicate")
    data = res.json()
    assert data["status"] == "ok", data
    new_id = data["project_id"]
    assert new_id != source_id
    assert data["name"] == "Dup Source V2"
    assert data["redirect_url"] == f"/projects/{new_id}"

    assert adi.get_project(source_id) is not None
    clone = adi.get_project(new_id)
    assert clone is not None
    assert clone.name == "Dup Source V2"
    assert clone.acceptance_status == "pending"
    assert clone.revision_count == 0
    assert clone.pending_revision_id is None

    clone_root = adi.project_path(new_id)
    assert (clone_root / "spec" / "SPEC.md").exists()
    assert (clone_root / "src" / "main.py").exists()
    assert (clone_root / "preview" / "mobile-mockup.html").exists()
    assert not (clone_root / "revisions").exists()
    clone_manifest = json.loads((clone_root / "manifest.json").read_text(encoding="utf-8"))
    assert clone_manifest["cloned_from"] == source_id

    adi.delete_project(new_id)
    adi.delete_project(source_id)
    print("[OK] duplicate_project API copies artifacts and resets revision state")


def main() -> int:
    print("=== Duplicate project tests ===\n")
    try:
        test_suggest_duplicate_name()
        test_duplicate_project_api()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        raise
    print("\n=== All duplicate project tests passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())