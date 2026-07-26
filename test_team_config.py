#!/usr/bin/env python3
"""Tests for agent team prompt/config management."""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

from ade.core.agent_team import AgentRole, DEFAULT_MODELS
from ade.core.team_config import TeamConfigManager, get_workflow_prompt


def test_prompts_materialized() -> None:
    root = Path("/tmp") / f"ade-team-{uuid.uuid4().hex[:8]}"
    mgr = TeamConfigManager(root=root)
    for role in AgentRole:
        prompt_path = mgr.prompts_dir / f"{role.value}.md"
        assert prompt_path.exists(), role.value
        assert mgr.read_role_prompt(role)
    assert (mgr.config_path).exists()
    shutil.rmtree(root, ignore_errors=True)
    print("[OK] Prompt MD files materialized")


def test_custom_prompt_and_model() -> None:
    root = Path("/tmp") / f"ade-team-{uuid.uuid4().hex[:8]}"
    mgr = TeamConfigManager(root=root)
    mgr.write_role_prompt(AgentRole.CODER, "Custom coder prompt for test.")
    mgr.set_model(AgentRole.CODER, "openrouter/test/model")
    team = mgr.build_team()
    assert team.get(AgentRole.CODER).system_prompt == "Custom coder prompt for test."
    assert team.get(AgentRole.CODER).model == "openrouter/test/model"
    assert mgr.is_role_customized(AgentRole.CODER)
    shutil.rmtree(root, ignore_errors=True)
    print("[OK] Custom prompt and model")


def test_reset_to_defaults() -> None:
    root = Path("/tmp") / f"ade-team-{uuid.uuid4().hex[:8]}"
    mgr = TeamConfigManager(root=root)
    mgr.write_role_prompt(AgentRole.TESTER, "Broken tester")
    mgr.set_model(AgentRole.TESTER, "custom/model")
    mgr.reset_to_defaults()
    assert mgr.read_role_prompt(AgentRole.TESTER) == mgr.read_role_default_prompt(AgentRole.TESTER)
    assert mgr.get_model(AgentRole.TESTER) == DEFAULT_MODELS[AgentRole.TESTER]
    assert not mgr.is_role_customized(AgentRole.TESTER)
    shutil.rmtree(root, ignore_errors=True)
    print("[OK] Reset to defaults")


def test_workflow_prompt_format() -> None:
    root = Path("/tmp") / f"ade-team-{uuid.uuid4().hex[:8]}"
    mgr = TeamConfigManager(root=root)
    text = get_workflow_prompt("coder-implement", spec="SPEC BODY")
    assert "SPEC BODY" in text
    shutil.rmtree(root, ignore_errors=True)
    print("[OK] Workflow prompt format")


def main() -> int:
    print("=== Team config tests ===\n")
    try:
        test_prompts_materialized()
        test_custom_prompt_and_model()
        test_reset_to_defaults()
        test_workflow_prompt_format()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        raise
    print("\n=== All team config tests passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())