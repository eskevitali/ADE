"""Agent team definitions for ADE v4 multi-agent harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AgentRole(str, Enum):
    """Specialized roles in the ADE development cycle."""

    SUPERVISOR = "supervisor"
    ARCHITECT = "architect"
    CODER = "coder"
    REVIEWER = "reviewer"
    TESTER = "tester"
    DEPLOYER = "deployer"


DEFAULT_MODELS: dict[AgentRole, str] = {
    AgentRole.SUPERVISOR: "openrouter/anthropic/claude-sonnet-4",
    AgentRole.ARCHITECT: "openrouter/anthropic/claude-sonnet-4",
    AgentRole.CODER: "openrouter/x-ai/grok-3",
    AgentRole.REVIEWER: "openrouter/anthropic/claude-sonnet-4",
    AgentRole.TESTER: "openrouter/openai/gpt-4.1",
    AgentRole.DEPLOYER: "openrouter/x-ai/grok-3",
}


DEFAULT_PROMPTS: dict[AgentRole, str] = {
    AgentRole.SUPERVISOR: (
        "You are the Supervisor of an autonomous development team. "
        "Analyze the task, decide which specialist should act next, "
        "and keep the workflow moving toward a deployable result."
    ),
    AgentRole.ARCHITECT: (
        "You are the Architect. Produce clear specifications, "
        "system design, and implementation plans."
    ),
    AgentRole.CODER: (
        "You are the Coder. Implement the plan with clean, modular, "
        "well-documented code following project rules."
    ),
    AgentRole.REVIEWER: (
        "You are the Reviewer. Inspect code and design for bugs, "
        "security issues, and adherence to PROJECT_RULES."
    ),
    AgentRole.TESTER: (
        "You are the Tester. Define and run tests, diagnose deploy and runtime "
        "failures, and recommend automated recovery (retry deploy vs code fix). "
        "Never ask the end user to fix bugs."
    ),
    AgentRole.DEPLOYER: (
        "You are the Deployer. Prepare Docker configuration and "
        "deployment steps for the deliverable."
    ),
}


ROLE_DESCRIPTIONS: dict[AgentRole, str] = {
    AgentRole.SUPERVISOR: "Routes tasks between specialists",
    AgentRole.ARCHITECT: "Specification and system design",
    AgentRole.CODER: "Implementation",
    AgentRole.REVIEWER: "Code review and quality gates",
    AgentRole.TESTER: "Testing and validation",
    AgentRole.DEPLOYER: "Docker and deployment",
}


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for a single agent role."""

    role: AgentRole
    name: str
    model: str
    system_prompt: str
    description: str = ""


@dataclass
class AgentTeam:
    """Collection of agents that form the ADE harness team."""

    agents: dict[AgentRole, AgentConfig] = field(default_factory=dict)

    @classmethod
    def default(cls, models: dict[AgentRole, str] | None = None) -> AgentTeam:
        """Build the standard team with optional per-role model overrides."""
        overrides = models or {}
        team: dict[AgentRole, AgentConfig] = {}
        for role in AgentRole:
            team[role] = AgentConfig(
                role=role,
                name=role.value.capitalize(),
                model=overrides.get(role, DEFAULT_MODELS[role]),
                system_prompt=DEFAULT_PROMPTS[role],
                description=ROLE_DESCRIPTIONS[role],
            )
        return cls(agents=team)

    def get(self, role: AgentRole) -> AgentConfig:
        if role not in self.agents:
            raise KeyError(f"Agent role not configured: {role}")
        return self.agents[role]

    def roles(self) -> list[AgentRole]:
        return list(self.agents.keys())

    def worker_roles(self) -> list[AgentRole]:
        """All roles except supervisor."""
        return [role for role in self.agents if role != AgentRole.SUPERVISOR]
