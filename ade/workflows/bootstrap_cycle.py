"""Dev Cycle with phased HITL: idea → ТЗ → spec → code → deliverable."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage

from ade.core.agent_team import AgentTeam
from ade.core.approval_gate import ApprovalGate, GateStatus, approval_gate
from ade.core.adi_manager import ADIManager
from ade.core.deliverable import (
    build_deliverable,
    ensure_expo_project,
    ensure_mobile_mockup,
    ensure_timer_simulator,
    needs_interactive_simulator,
    write_deliverable_manifest,
)
from ade.workflows.dev_cycle import (
    DevCycleOrchestrator,
    DevCycleState,
    _coder_node,
    _reviewer_node,
)
from ade.workflows.hitl_helpers import generate_spec_from_tz, generate_tz

EventCallback = Callable[[str, dict[str, Any]], None]

APPROVAL_GATES = ("idea", "tz", "spec", "code")


class BootstrapCycleOrchestrator(DevCycleOrchestrator):
    """Idea discussion → ТЗ → Spec → Coder → Reviewer → Deliverable preview."""

    def __init__(
        self,
        team: AgentTeam | None = None,
        on_event: EventCallback | None = None,
        *,
        task_id: str,
        project_id: str,
        adi_manager: ADIManager | None = None,
        gate: ApprovalGate | None = None,
        human_in_loop: bool = True,
        gate_timeout: float | None = None,
        discussion: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(team=team, on_event=on_event)
        self.task_id = task_id
        self.project_id = project_id
        self.adi = adi_manager or ADIManager()
        self.gate = gate or approval_gate
        self.human_in_loop = human_in_loop
        self.gate_timeout = gate_timeout
        self.discussion = discussion or []

    def _wait_for_approval(self, gate_name: str, state: DevCycleState) -> GateStatus:
        self.gate.open(self.task_id, gate_name)
        self.on_event(
            "awaiting_approval",
            {
                "gate": gate_name,
                "phase": state.get("phase", ""),
                "task_id": self.task_id,
                "project_id": self.project_id,
            },
        )
        status = self.gate.wait(self.task_id, gate_name, timeout=self.gate_timeout)
        self.on_event(
            "approval_resolved",
            {"gate": gate_name, "status": status.value, "task_id": self.task_id},
        )
        return status

    def _handle_gate_result(self, state: DevCycleState, approval: GateStatus) -> bool:
        if approval == GateStatus.REJECTED:
            state["status"] = "rejected"
            self.on_event("workflow_completed", {"status": "rejected"})
            return False
        if approval == GateStatus.TIMEOUT:
            state["status"] = "timeout"
            self.on_event("workflow_completed", {"status": "timeout"})
            return False
        return True

    def run(self, task: str) -> DevCycleState:
        coder = _coder_node(self.team)
        reviewer = _reviewer_node(self.team)

        state: DevCycleState = {
            "messages": [HumanMessage(content=task)],
            "task": task,
            "phase": "idea",
            "spec": "",
            "code": "",
            "review": "",
            "status": "running",
        }
        tz = ""

        self.on_event("workflow_started", {"task": task, "project_id": self.project_id})

        if self.human_in_loop:
            state["phase"] = "idea_discussion"
            self.on_event("step_completed", {"node": "idea", "phase": "idea_discussion", "status": "discussing"})
            approval = self._wait_for_approval("idea", state)
            if not self._handle_gate_result(state, approval):
                return state

        tz = generate_tz(self.team, task, self.discussion)
        state["phase"] = "tz"
        self.adi.write_tz(self.project_id, tz)
        self.on_event(
            "document_ready",
            {"gate": "tz", "document": tz, "task_id": self.task_id},
        )
        self.on_event("step_completed", {"node": "architect", "phase": "tz", "status": "tz_ready"})

        if self.human_in_loop:
            approval = self._wait_for_approval("tz", state)
            if not self._handle_gate_result(state, approval):
                return state
            tz_path = self.adi.project_path(self.project_id) / "spec" / "TZ.md"
            if tz_path.exists():
                tz = tz_path.read_text(encoding="utf-8")

        spec = generate_spec_from_tz(self.team, task, tz)
        state["spec"] = spec
        state["phase"] = "spec"
        self.adi.write_spec(self.project_id, spec)
        self.on_event(
            "document_ready",
            {"gate": "spec", "document": spec, "task_id": self.task_id},
        )
        self.on_event("step_completed", {"node": "architect", "phase": "spec", "status": "spec_ready"})

        if self.human_in_loop:
            approval = self._wait_for_approval("spec", state)
            if not self._handle_gate_result(state, approval):
                return state
            spec_path = self.adi.project_path(self.project_id) / "spec" / "SPEC.md"
            if spec_path.exists():
                state["spec"] = spec_path.read_text(encoding="utf-8")

        state = {**state, **coder(state)}
        self.adi.write_code(self.project_id, state["code"])
        self.on_event(
            "step_completed",
            {"node": "coder", "phase": "code", "status": state["status"]},
        )

        if self.human_in_loop:
            approval = self._wait_for_approval("code", state)
            if not self._handle_gate_result(state, approval):
                return state

        state = {**state, **reviewer(state)}
        self.adi.write_review(self.project_id, state["review"])
        self.on_event(
            "step_completed",
            {"node": "reviewer", "phase": "review", "status": state["status"]},
        )

        project = self.adi.get_project(self.project_id)
        project_path = self.adi.project_path(self.project_id)
        deliverable = build_deliverable(
            self.project_id,
            project.name if project else "ADI",
            task,
            state["spec"],
            state["code"],
            project_path,
        )
        if needs_interactive_simulator(task, state["spec"], code=state["code"]):
            ensure_timer_simulator(project_path, deliverable["project_name"], state["spec"])
            deliverable = build_deliverable(
                self.project_id,
                project.name if project else "ADI",
                task,
                state["spec"],
                state["code"],
                project_path,
            )
        elif deliverable["type"] == "mobile":
            ensure_mobile_mockup(project_path, deliverable["project_name"], state["spec"])
            ensure_expo_project(project_path, deliverable["project_name"], state["spec"])
            deliverable = build_deliverable(
                self.project_id,
                project.name if project else "ADI",
                task,
                state["spec"],
                state["code"],
                project_path,
            )
        write_deliverable_manifest(project_path, deliverable)
        self.on_event("deliverable_ready", deliverable)
        self.on_event("workflow_completed", {"status": state.get("status", "completed")})
        return state