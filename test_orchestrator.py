#!/usr/bin/env python3
"""Smoke test for AgentTeam and orchestrator workflow."""

from __future__ import annotations

import os
import sys

from ade.core.agent_team import AgentRole, AgentTeam
from ade.workflows.orchestrator import DevOrchestrator, build_orchestrator


def test_agent_team() -> None:
    team = AgentTeam.default()
    roles = team.roles()
    assert len(roles) == 6, f"expected 6 roles, got {len(roles)}"

    for role in AgentRole:
        cfg = team.get(role)
        assert cfg.name, f"missing name for {role}"
        assert cfg.model, f"missing model for {role}"
        assert cfg.system_prompt, f"missing prompt for {role}"

    workers = team.worker_roles()
    assert AgentRole.SUPERVISOR not in workers
    assert len(workers) == 5
    print("[OK] AgentTeam: 6 roles configured, 5 workers")


def test_orchestrator_compile() -> None:
    team = AgentTeam.default()
    graph = build_orchestrator(team, max_iterations=3)
    assert graph is not None
    print("[OK] Orchestrator graph compiled")


def test_workflow_run() -> None:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        print("[SKIP] Workflow run: OPENROUTER_API_KEY not set")
        return

    orch = DevOrchestrator(max_iterations=2)
    result = orch.run("Напиши одно предложение: что такое ADE v4.")
    assert result["task"]
    assert result["iteration"] >= 0
    assert len(result["messages"]) >= 1
    print(f"[OK] Workflow run: status={result['status']}, iterations={result['iteration']}")


def main() -> int:
    print("=== ADE v4 Orchestrator Test ===\n")
    try:
        test_agent_team()
        test_orchestrator_compile()
        test_workflow_run()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1

    print("\n=== All checks passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
