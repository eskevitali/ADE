#!/usr/bin/env python3
"""Tests for Tester-driven recovery loop."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from ade.core.adi_manager import ADIManager
from ade.core.config import get_config
from ade.workflows.recovery import (
    FailureContext,
    RecoveryAction,
    RecoveryService,
    classify_failure_heuristic,
)
from ade.workflows.revision_rebuild import RevisionRebuildOrchestrator

PASS_CODE = "print('ok')\n"
FAIL_CODE = "def broken(\n"


def _bootstrap_project(adi: ADIManager, project_id: str) -> None:
    adi.bootstrap(project_id, "Recovery Test", "test idea", enable_isolation=False)
    adi.write_spec(project_id, "# Spec\n", update_status=False)
    adi.write_tz(project_id, "# TZ\n", update_status=False)
    (adi.project_path(project_id) / "src" / "main.py").write_text(PASS_CODE, encoding="utf-8")
    manifest = adi._read_manifest(project_id)
    manifest["status"] = "rebuilding"
    manifest["rebuild_status"] = "queued"
    adi._write_manifest(project_id, manifest)
    rev_path = adi.revisions_dir(project_id) / "rev-1.json"
    rev_path.write_text(
        json.dumps({"id": 1, "feedback": "fix", "confirmed": True}),
        encoding="utf-8",
    )


def test_heuristic_syntax_error() -> None:
    ctx = FailureContext(
        failure_type="deploy",
        phase="deploy",
        error="SyntaxError: invalid syntax",
        attempt=1,
        max_attempts=3,
    )
    decision = classify_failure_heuristic(ctx)
    assert decision is not None
    assert decision.action == RecoveryAction.FIX_CODE
    print("[OK] Syntax error → fix_code")


def test_heuristic_compose_error() -> None:
    ctx = FailureContext(
        failure_type="deploy",
        phase="deploy",
        error="empty compose file",
        attempt=1,
        max_attempts=3,
    )
    decision = classify_failure_heuristic(ctx)
    assert decision is not None
    assert decision.action == RecoveryAction.RETRY_DEPLOY
    print("[OK] Compose error → retry_deploy")


def test_recovery_limit_escalates() -> None:
    service = RecoveryService()
    ctx = FailureContext(
        failure_type="deploy",
        phase="deploy",
        error="unknown weird failure",
        attempt=3,
        max_attempts=3,
    )
    decision = service.decide(ctx)
    assert decision.action == RecoveryAction.ESCALATE
    print("[OK] Max attempts → escalate")


def test_adi_recovery_counters() -> None:
    config = get_config()
    adi = ADIManager()
    project_id = f"recovery-{uuid.uuid4().hex[:8]}"
    _bootstrap_project(adi, project_id)

    adi.reset_recovery(project_id)
    assert adi.recovery_limit(project_id) == config.max_recovery_attempts

    attempt, limit = adi.begin_recovery_attempt(
        project_id,
        phase="retry_deploy",
        decision="retry_deploy",
        message="retry",
    )
    assert attempt == 1
    assert limit == config.max_recovery_attempts
    project = adi.get_project(project_id)
    assert project is not None
    assert project.recovery_status == "recovering"
    assert project.rebuild_status == "recovering"

    adi.escalate_recovery(project_id, error="still broken", message="give up")
    project = adi.get_project(project_id)
    assert project is not None
    assert project.recovery_status == "escalated"
    assert project.rebuild_status == "failed"
    print("[OK] ADIManager recovery counters")


def test_revision_rebuild_retries_deploy_then_succeeds() -> None:
    adi = ADIManager()
    project_id = f"recovery-{uuid.uuid4().hex[:8]}"
    _bootstrap_project(adi, project_id)

    deploy_calls = {"n": 0}

    def fake_deploy(project_id: str, *, use_agent: bool = False) -> dict:
        deploy_calls["n"] += 1
        if deploy_calls["n"] == 1:
            manifest = adi._read_manifest(project_id)
            manifest["deploy_error"] = "empty compose file"
            adi._write_manifest(project_id, manifest)
            return {"status": "failed", "message": "deploy_failed"}
        return {"status": "running", "message": "deployed"}

    coder = MagicMock(return_value={"code": PASS_CODE, "status": "code_ready", "phase": "code"})
    reviewer = MagicMock(return_value={"review": "ok", "status": "completed", "phase": "review"})

    with (
        patch("ade.workflows.revision_rebuild._coder_node", return_value=coder),
        patch("ade.workflows.revision_rebuild._reviewer_node", return_value=reviewer),
        patch.object(adi, "deploy_project", side_effect=fake_deploy),
        patch(
            "ade.workflows.revision_rebuild.build_deliverable",
            return_value={"type": "web", "files": []},
        ),
        patch("ade.workflows.revision_rebuild.write_deliverable_manifest"),
    ):
        orch = RevisionRebuildOrchestrator(adi_manager=adi)
        result = orch.run(project_id, 1)

    assert result["status"] == "completed"
    assert deploy_calls["n"] == 2
    project = adi.get_project(project_id)
    assert project is not None
    assert project.rebuild_status == "completed"
    assert project.recovery_attempts == 1
    print("[OK] Recovery loop retries deploy then succeeds")


def test_revision_rebuild_escalates_after_limit() -> None:
    adi = ADIManager()
    project_id = f"recovery-{uuid.uuid4().hex[:8]}"
    _bootstrap_project(adi, project_id)
    manifest = adi._read_manifest(project_id)
    manifest["recovery_max_attempts"] = 2
    adi._write_manifest(project_id, manifest)

    def always_fail(project_id: str, *, use_agent: bool = False) -> dict:
        manifest = adi._read_manifest(project_id)
        manifest["deploy_error"] = "SyntaxError: invalid syntax"
        adi._write_manifest(project_id, manifest)
        return {"status": "failed", "message": "deploy_failed"}

    coder = MagicMock(return_value={"code": FAIL_CODE, "status": "code_ready", "phase": "code"})
    reviewer = MagicMock(return_value={"review": "ok", "status": "completed", "phase": "review"})

    with (
        patch("ade.workflows.revision_rebuild._coder_node", return_value=coder),
        patch("ade.workflows.revision_rebuild._reviewer_node", return_value=reviewer),
        patch.object(adi, "deploy_project", side_effect=always_fail),
        patch(
            "ade.workflows.revision_rebuild.build_deliverable",
            return_value={"type": "web", "files": []},
        ),
        patch("ade.workflows.revision_rebuild.write_deliverable_manifest"),
    ):
        orch = RevisionRebuildOrchestrator(adi_manager=adi)
        result = orch.run(project_id, 1)

    assert result["status"] == "escalated"
    project = adi.get_project(project_id)
    assert project is not None
    assert project.recovery_status == "escalated"
    assert project.rebuild_status == "failed"
    assert project.recovery_attempts == 2
    print("[OK] Recovery escalates after limit")


def main() -> int:
    print("=== Recovery loop tests ===\n")
    try:
        test_heuristic_syntax_error()
        test_heuristic_compose_error()
        test_recovery_limit_escalates()
        test_adi_recovery_counters()
        test_revision_rebuild_retries_deploy_then_succeeds()
        test_revision_rebuild_escalates_after_limit()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        raise
    print("\n=== All recovery loop tests passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())