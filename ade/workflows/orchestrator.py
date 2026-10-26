"""Basic LangGraph orchestrator with supervisor routing."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from ade.core.agent_team import AgentRole, AgentTeam
from ade.core.llm_provider import get_llm
from ade.core.team_config import get_workflow_prompt
from ade.core.policy_context import organizational_context

WORKER_NODES = {
    AgentRole.ARCHITECT: "architect",
    AgentRole.CODER: "coder",
    AgentRole.REVIEWER: "reviewer",
    AgentRole.TESTER: "tester",
    AgentRole.DEPLOYER: "deployer",
}

NODE_TO_ROLE = {node: role for role, node in WORKER_NODES.items()}


class WorkflowState(TypedDict):
    """Shared state for the development workflow graph."""

    messages: Annotated[list[BaseMessage], add_messages]
    task: str
    next_agent: str
    iteration: Annotated[int, operator.add]
    max_iterations: int
    status: str


class DevOrchestrator:
    """Supervisor-based multi-agent orchestrator."""

    def __init__(self, team: AgentTeam | None = None, max_iterations: int = 10) -> None:
        self.team = team or AgentTeam.default()
        self.max_iterations = max_iterations
        self.graph = build_orchestrator(self.team, max_iterations=max_iterations)

    def run(self, task: str) -> WorkflowState:
        """Execute the workflow for a given task description."""
        initial: WorkflowState = {
            "messages": [HumanMessage(content=task)],
            "task": task,
            "next_agent": "architect",
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "status": "running",
        }
        return self.graph.invoke(initial)


def _make_agent_node(role: AgentRole, team: AgentTeam):
    config = team.get(role)

    def node(state: WorkflowState) -> dict:
        llm = get_llm(config.model)
        response = llm.invoke(
            [
                SystemMessage(content=config.system_prompt + "\n\n" + organizational_context(state["task"])),
                *state["messages"],
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        return {
            "messages": [
                AIMessage(content=content, name=config.name),
            ],
            "iteration": 1,
        }

    return node


def _supervisor_node(team: AgentTeam):
    supervisor = team.get(AgentRole.SUPERVISOR)

    def node(state: WorkflowState) -> dict:
        if state["iteration"] >= state["max_iterations"]:
            return {"next_agent": "finish", "status": "max_iterations_reached"}

        llm = get_llm(supervisor.model)
        workers = ", ".join(WORKER_NODES.values())
        prompt = (
            f"{supervisor.system_prompt}\n\n{organizational_context(state['task'])}\n\n"
            f"Task: {state['task']}\n"
            f"Available workers: {workers}\n"
            f"{get_workflow_prompt('supervisor-route')}"
        )
        response = llm.invoke([SystemMessage(content=prompt), *state["messages"]])
        raw = response.content if isinstance(response.content, str) else str(response.content)
        choice = raw.strip().lower().split()[0] if raw.strip() else "finish"
        if choice not in WORKER_NODES.values():
            choice = "finish"
        return {"next_agent": choice, "status": "routing"}

    return node


def _route_supervisor(state: WorkflowState) -> Literal[
    "architect", "coder", "reviewer", "tester", "deployer", "finish"
]:
    nxt = state.get("next_agent", "finish")
    if nxt in WORKER_NODES.values():
        return nxt  # type: ignore[return-value]
    return "finish"


def build_orchestrator(team: AgentTeam | None = None, *, max_iterations: int = 10):
    """Compile the supervisor LangGraph workflow."""
    team = team or AgentTeam.default()
    graph = StateGraph(WorkflowState)

    graph.add_node("supervisor", _supervisor_node(team))
    for role, node_name in WORKER_NODES.items():
        graph.add_node(node_name, _make_agent_node(role, team))

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route_supervisor,
        {**{node: node for node in WORKER_NODES.values()}, "finish": END},
    )
    for node_name in WORKER_NODES.values():
        graph.add_edge(node_name, "supervisor")

    return graph.compile()
