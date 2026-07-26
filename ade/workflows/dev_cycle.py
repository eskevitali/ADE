"""First real ADE workflow: Idea → Spec → Code → Review."""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from ade.core.agent_team import AgentRole, AgentTeam
from ade.core.llm_provider import get_llm
from ade.core.team_config import get_workflow_prompt

EventCallback = Callable[[str, dict[str, Any]], None]

PHASES = ("architect", "coder", "reviewer")


class DevCycleState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    task: str
    phase: str
    spec: str
    code: str
    review: str
    status: str


def _invoke_agent(team: AgentTeam, role: AgentRole, state: DevCycleState, extra: str = "") -> str:
    config = team.get(role)
    llm = get_llm(config.model)
    system = config.system_prompt
    if extra:
        system = f"{system}\n\n{extra}"
    response = llm.invoke([SystemMessage(content=system), *state["messages"]])
    content = response.content if isinstance(response.content, str) else str(response.content)
    return content


def _architect_node(team: AgentTeam):
    def node(state: DevCycleState) -> dict:
        content = _invoke_agent(
            team,
            AgentRole.ARCHITECT,
            state,
            get_workflow_prompt("architect-spec-task"),
        )
        return {
            "messages": [AIMessage(content=content, name="Architect")],
            "spec": content,
            "phase": "spec",
            "status": "spec_ready",
        }

    return node


def _coder_node(team: AgentTeam):
    def node(state: DevCycleState) -> dict:
        extra = get_workflow_prompt("coder-implement", spec=state.get("spec", ""))
        content = _invoke_agent(team, AgentRole.CODER, state, extra)
        return {
            "messages": [AIMessage(content=content, name="Coder")],
            "code": content,
            "phase": "code",
            "status": "code_ready",
        }

    return node


def _reviewer_node(team: AgentTeam):
    def node(state: DevCycleState) -> dict:
        extra = get_workflow_prompt(
            "reviewer-review",
            spec=state.get("spec", ""),
            code=state.get("code", ""),
        )
        content = _invoke_agent(team, AgentRole.REVIEWER, state, extra)
        return {
            "messages": [AIMessage(content=content, name="Reviewer")],
            "review": content,
            "phase": "review",
            "status": "completed",
        }

    return node


def build_dev_cycle(team: AgentTeam | None = None):
    team = team or AgentTeam.default()
    graph = StateGraph(DevCycleState)

    graph.add_node("architect", _architect_node(team))
    graph.add_node("coder", _coder_node(team))
    graph.add_node("reviewer", _reviewer_node(team))

    graph.add_edge(START, "architect")
    graph.add_edge("architect", "coder")
    graph.add_edge("coder", "reviewer")
    graph.add_edge("reviewer", END)

    return graph.compile()


class DevCycleOrchestrator:
    """Linear development workflow with optional event streaming."""

    def __init__(
        self,
        team: AgentTeam | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        self.team = team or AgentTeam.default()
        self.on_event = on_event or (lambda _event, _data: None)
        self.graph = build_dev_cycle(self.team)

    def run(self, task: str) -> DevCycleState:
        initial: DevCycleState = {
            "messages": [HumanMessage(content=task)],
            "task": task,
            "phase": "idea",
            "spec": "",
            "code": "",
            "review": "",
            "status": "running",
        }
        self.on_event("workflow_started", {"task": task})
        final: DevCycleState = initial
        prev_phase = initial["phase"]
        for state in self.graph.stream(initial, stream_mode="values"):
            final = state
            phase = state.get("phase", prev_phase)
            if phase != prev_phase:
                self.on_event(
                    "step_completed",
                    {
                        "node": phase,
                        "phase": phase,
                        "status": state.get("status", "running"),
                    },
                )
                prev_phase = phase
        self.on_event("workflow_completed", {"status": final.get("status", "completed")})
        return final
