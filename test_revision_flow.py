#!/usr/bin/env python3
"""Tests for revision review → confirm → rebuild flow."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ade.core.adi_manager import ADIManager
from ade.core.config import get_config
from ade.core.deliverable import _extract_button_label, ensure_mobile_mockup
from ade.ui.main import app

V2_ID = "203941da-7cd3-430d-b26a-f8bf9fe3b178"


def _login(client: TestClient) -> None:
    config = get_config()
    client.post(
        "/auth/login",
        data={"username": config.admin_username, "password": config.admin_password},
        follow_redirects=True,
    )


def test_backfill_pending_revision() -> None:
    adi = ADIManager()
    rev_id = adi.ensure_pending_revision_record(V2_ID)
    assert rev_id == 1
    project = adi.get_project(V2_ID)
    assert project is not None
    assert project.pending_revision_id == 1
    assert project.status == "revision_review"
    assert project.acceptance_status == "pending_review"
    rev_path = adi.project_path(V2_ID) / "revisions" / "rev-1.json"
    assert rev_path.exists()
    print("[OK] Backfill pending revision for V2")


def test_mobile_mockup_button_label() -> None:
    label = _extract_button_label("", 'Изменить надпись на кнопке на "Я ТУТ"')
    assert label == "Я ТУТ"
    config = get_config()
    tmp = config.projects_dir / "mockup-test"
    tmp.mkdir(parents=True, exist_ok=True)
    path = ensure_mobile_mockup(tmp, "Test", "", feedback='кнопка "Я ТУТ"')
    html = path.read_text(encoding="utf-8")
    assert "Я ТУТ" in html
    assert "Техническая спецификация" not in html
    print("[OK] Mobile mockup uses button label without spec dump")


def test_confirm_starts_rebuild() -> None:
    client = TestClient(app)
    _login(client)
    project_id = "658fbae8-5606-42f6-858a-5b2cdd0d33be"
    adi = ADIManager()

    rev_path = adi.revisions_dir(project_id) / "rev-1.json"
    if rev_path.exists():
        record = json.loads(rev_path.read_text(encoding="utf-8"))
        record["confirmed"] = False
        record.pop("confirmed_at", None)
        rev_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest = adi._read_manifest(project_id)
    manifest["pending_revision_id"] = 1
    manifest["acceptance_status"] = "pending_review"
    manifest["status"] = "revision_review"
    manifest.pop("rebuild_status", None)
    adi._write_manifest(project_id, manifest)

    with patch("ade.ui.main._run_revision_rebuild") as mock_rebuild:
        import asyncio

        async def noop(*_a, **_k):
            return None

        mock_rebuild.side_effect = noop

        res = client.post(f"/api/projects/{project_id}/revision/1/confirm")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "rebuild=1" in data["redirect_url"]
        assert data["rebuild_status"] == "started"

    manifest = json.loads((adi.project_path(project_id) / "manifest.json").read_text())
    assert manifest["rebuild_status"] == "queued"
    assert manifest["pending_revision_id"] is None
    rev = adi.get_revision(project_id, 1)
    assert rev and rev.get("confirmed") is True
    print("[OK] Confirm revision queues rebuild")


def test_revise_redirects_when_pending_review() -> None:
    client = TestClient(app)
    _login(client)
    adi = ADIManager()
    adi.ensure_pending_revision_record(V2_ID)

    res = client.post(
        f"/api/projects/{V2_ID}/revise",
        json={"feedback": "ещё одна правка"},
    )
    data = res.json()
    assert data["status"] == "error"
    assert data["message"] == "pending_review"
    assert f"/revision/1" in data["redirect_url"]
    print("[OK] Revise blocked until pending review confirmed")


def main() -> int:
    print("=== Revision flow tests ===\n")
    try:
        test_backfill_pending_revision()
        test_mobile_mockup_button_label()
        test_confirm_starts_rebuild()
        test_revise_redirects_when_pending_review()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        raise
    print("\n=== All revision flow tests passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())