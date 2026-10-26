"""Post-revision pipeline: code regen → review → deliverable → deploy."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from ade.core.agent_team import AgentTeam
from ade.core.adi_manager import ADIManager
from ade.core.deliverable import (
    build_deliverable,
    ensure_expo_project,
    ensure_mobile_mockup,
    ensure_timer_simulator,
    needs_interactive_simulator,
    write_deliverable_manifest,
)
from ade.workflows.dev_cycle import DevCycleState, _coder_node, _reviewer_node
from ade.workflows.recovery import FailureContext, RecoveryAction, RecoveryService

logger = logging.getLogger(__name__)

EventCallback = Callable[[str, dict[str, Any]], None]


class RevisionRebuildOrchestrator:
    """Rebuild code and deploy after a confirmed TZ/Spec revision."""

    def __init__(
        self,
        team: AgentTeam | None = None,
        adi_manager: ADIManager | None = None,
        on_event: EventCallback | None = None,
        recovery: RecoveryService | None = None,
    ) -> None:
        self.team = team or AgentTeam.default()
        self.adi = adi_manager or ADIManager()
        self.on_event = on_event or (lambda _event, _data: None)
        self.recovery = recovery or RecoveryService(self.team)

    def run(self, project_id: str, revision_id: int) -> dict[str, Any]:
        project = self.adi.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        revision = self.adi.get_revision(project_id, revision_id)
        feedback = revision.get("feedback", "") if revision else ""

        detail = self.adi.get_project_detail(project_id)
        if not detail:
            raise ValueError(f"Project detail {project_id} not found")

        spec = detail["spec"]
        task = project.idea
        project_path = self.adi.project_path(project_id)
        design_brief = project_path / "spec" / "DESIGN.md"
        if design_brief.is_file():
            task += "\n\n" + design_brief.read_text()

        self.adi.reset_recovery(project_id)
        self.adi.set_rebuild_status(
            project_id, "rebuilding", revision_id=revision_id, phase="coder"
        )
        self.on_event(
            "rebuild_started",
            {"project_id": project_id, "revision_id": revision_id, "phase": "coder"},
        )

        coder = _coder_node(self.team)
        reviewer = _reviewer_node(self.team)

        state: DevCycleState = {
            "messages": [HumanMessage(content=task)],
            "task": task,
            "phase": "code",
            "spec": spec,
            "code": "",
            "review": "",
            "status": "running",
        }

        deliverable: dict[str, Any] = {}
        rerun_from_coder = True

        while True:
            try:
                if rerun_from_coder:
                    state, deliverable = self._run_code_phases(
                        project_id,
                        feedback,
                        spec,
                        task,
                        project_path,
                        project.name,
                        coder,
                        reviewer,
                        state,
                    )
                deploy_result = self._deploy_only(project_id, revision_id)
            except Exception as exc:
                outcome = self._handle_failure(
                    project_id,
                    revision_id,
                    failure_type="rebuild",
                    phase=state.get("phase", "unknown"),
                    error=str(exc),
                    spec=spec,
                    code=state.get("code", ""),
                )
                if outcome == "escalated":
                    return {"status": "escalated", "error": str(exc), "deliverable": deliverable}
                rerun_from_coder = outcome == "fix_code"
                if rerun_from_coder:
                    state = self._inject_fix_hint(state, project_id)
                continue

            deploy_status = deploy_result.get("status", "")
            if deploy_status not in ("failed", "error"):
                break

            manifest = self.adi._read_manifest(project_id)
            outcome = self._handle_failure(
                project_id,
                revision_id,
                failure_type="deploy",
                phase="deploy",
                error=deploy_result.get("message", "deploy_failed"),
                spec=spec,
                code=state.get("code", ""),
                deploy_error=manifest.get("deploy_error", ""),
            )
            if outcome == "escalated":
                return {
                    "status": "escalated",
                    "deploy": deploy_result,
                    "deliverable": deliverable,
                }
            rerun_from_coder = outcome == "fix_code"
            if rerun_from_coder:
                state = self._inject_fix_hint(state, project_id)

        self.adi.complete_rebuild(
            project_id,
            deploy_status=deploy_result.get("status", "unknown"),
        )
        self.on_event(
            "rebuild_completed",
            {
                "project_id": project_id,
                "revision_id": revision_id,
                "deploy_status": deploy_result.get("status"),
                "deliverable": deliverable,
            },
        )
        return {
            "status": "completed",
            "deploy": deploy_result,
            "deliverable": deliverable,
        }

    def _inject_fix_hint(self, state: DevCycleState, project_id: str) -> DevCycleState:
        manifest = self.adi._read_manifest(project_id)
        hint = manifest.get("recovery_message", "")
        if hint:
            state = {
                **state,
                "messages": [
                    *state["messages"],
                    AIMessage(
                        content=(
                            "Tester: предыдущий деплой/сборка упали. "
                            f"Исправь код по диагностике:\n{hint}"
                        ),
                        name="Tester",
                    ),
                ],
            }
        return state

    def _handle_failure(
        self,
        project_id: str,
        revision_id: int,
        *,
        failure_type: str,
        phase: str,
        error: str,
        spec: str,
        code: str,
        deploy_error: str = "",
    ) -> str:
        limit = self.adi.recovery_limit(project_id)
        manifest = self.adi._read_manifest(project_id)
        current = int(manifest.get("recovery_attempts", 0))
        ctx = FailureContext(
            failure_type=failure_type,
            phase=phase,
            error=error,
            attempt=current + 1,
            max_attempts=limit,
            spec=spec,
            code=code,
            deploy_error=deploy_error or error,
        )
        decision = self.recovery.decide(ctx)
        attempt, limit = self.adi.begin_recovery_attempt(
            project_id,
            phase=decision.action.value,
            decision=decision.action.value,
            message=decision.reason,
        )
        self.on_event(
            "recovery_started",
            {
                "project_id": project_id,
                "revision_id": revision_id,
                "attempt": attempt,
                "max_attempts": limit,
                "action": decision.action.value,
                "reason": decision.reason,
                "failure_type": failure_type,
            },
        )

        if decision.action == RecoveryAction.ESCALATE:
            self.adi.escalate_recovery(
                project_id,
                error=error,
                message=(
                    f"Автовосстановление исчерпано ({attempt}/{limit}). "
                    f"{decision.reason}"
                ),
            )
            self.on_event(
                "recovery_escalated",
                {
                    "project_id": project_id,
                    "revision_id": revision_id,
                    "attempt": attempt,
                    "max_attempts": limit,
                    "error": error[:500],
                },
            )
            return "escalated"

        label = {
            RecoveryAction.RETRY_DEPLOY: f"Tester: повтор деплоя ({attempt}/{limit})…",
            RecoveryAction.FIX_CODE: f"Tester: правка кода ({attempt}/{limit})…",
        }[decision.action]
        self.on_event(
            "recovery_action",
            {
                "project_id": project_id,
                "action": decision.action.value,
                "attempt": attempt,
                "label": label,
            },
        )
        return decision.action.value

    def _deploy_only(self, project_id: str, revision_id: int) -> dict[str, Any]:
        self.adi.set_rebuild_status(project_id, "recovering", phase="deploy")
        self.on_event(
            "rebuild_phase",
            {"project_id": project_id, "phase": "deploy", "label": "Повтор деплоя…"},
        )
        deploy_result = self.adi.deploy_project(project_id)
        self.on_event("deploy_completed", deploy_result)
        return deploy_result

    def _run_code_phases(
        self,
        project_id: str,
        feedback: str,
        spec: str,
        task: str,
        project_path: Any,
        project_name: str,
        coder: Any,
        reviewer: Any,
        state: DevCycleState,
    ) -> tuple[DevCycleState, dict[str, Any]]:
        self.adi.set_rebuild_status(project_id, "rebuilding", phase="coder")
        self.on_event(
            "rebuild_phase",
            {"project_id": project_id, "phase": "coder", "label": "Coder генерирует код…"},
        )
        state = {**state, **coder(state)}
        self.adi.write_code(project_id, state["code"], update_status=False)
        self.on_event(
            "step_completed",
            {"node": "coder", "phase": "code", "status": state["status"]},
        )

        self.adi.set_rebuild_status(project_id, "rebuilding", phase="reviewer")
        self.on_event(
            "rebuild_phase",
            {"project_id": project_id, "phase": "reviewer", "label": "Reviewer проверяет…"},
        )
        state = {**state, **reviewer(state)}
        self.adi.write_review(project_id, state["review"], update_status=False)
        self.on_event(
            "step_completed",
            {"node": "reviewer", "phase": "review", "status": state["status"]},
        )

        self.adi.set_rebuild_status(project_id, "rebuilding", phase="mockup")
        self.on_event(
            "rebuild_phase",
            {"project_id": project_id, "phase": "mockup", "label": "Обновление превью…"},
        )
        deliverable = build_deliverable(
            project_id,
            project_name,
            task,
            spec,
            state["code"],
            project_path,
        )
        if needs_interactive_simulator(task, spec, feedback=feedback, code=state["code"]):
            ensure_timer_simulator(
                project_path,
                project_name,
                spec,
                feedback=feedback,
            )
            deliverable = build_deliverable(
                project_id,
                project_name,
                task,
                spec,
                state["code"],
                project_path,
            )
        elif deliverable["type"] == "mobile":
            ensure_mobile_mockup(
                project_path,
                project_name,
                spec,
                feedback=feedback,
            )
            ensure_expo_project(
                project_path,
                project_name,
                spec,
                feedback=feedback,
            )
            deliverable = build_deliverable(
                project_id,
                project_name,
                task,
                spec,
                state["code"],
                project_path,
            )
        write_deliverable_manifest(project_path, deliverable)
        self.on_event("deliverable_ready", deliverable)
        return state, deliverable