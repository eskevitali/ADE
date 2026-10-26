"""Load and persist agent prompts (markdown) and per-role model overrides."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ade.core.agent_team import DEFAULT_MODELS, AgentRole, AgentTeam, ROLE_DESCRIPTIONS
from ade.core.config import get_config

WORKFLOW_PROMPT_NAMES = (
    "architect-discuss-idea",
    "architect-generate-tz",
    "architect-generate-spec",
    "architect-revise-section",
    "architect-revise-tz",
    "architect-revise-spec",
    "architect-spec-task",
    "coder-implement",
    "reviewer-review",
    "deployer-summarize",
    "tester-recovery-extra",
    "supervisor-route",
)

ROLE_DEFAULT_PROMPTS: dict[AgentRole, str] = {
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

WORKFLOW_DEFAULT_PROMPTS: dict[str, str] = {
    "architect-discuss-idea": (
        "You are in the IDEA DISCUSSION phase with the user. "
        "Clarify requirements, ask focused questions, suggest scope. "
        "Do NOT produce full technical specification yet — only discuss the product idea.\n\n"
        "Original idea:\n{idea}"
    ),
    "architect-generate-tz": (
        "Produce a concise TECHNICAL ASSIGNMENT (ТЗ) in Russian markdown. "
        "Use ## headings for each major section (Цели, Пользователи, Функции, "
        "Нефункциональные требования, Платформа, Ограничения). "
        "This is for user review before the full specification."
    ),
    "architect-generate-spec": (
        "Produce a detailed technical SPECIFICATION in Russian markdown based on the approved ТЗ. "
        "Use ## headings. Include architecture, APIs, data model, UI flows, acceptance criteria."
    ),
    "architect-revise-section": (
        "Revise ONLY the following section of the {doc_type} based on user feedback. "
        "Return ONLY the revised section body (no ## heading)."
    ),
    "architect-revise-tz": (
        "The user tested the deliverable and requests improvements. "
        "Revise the TECHNICAL ASSIGNMENT (ТЗ) in Russian markdown incorporating their feedback. "
        "Keep ## section structure. Address all user points."
    ),
    "architect-revise-spec": (
        "Update the full SPECIFICATION in Russian markdown to match the revised ТЗ and user feedback. "
        "Use ## headings. Keep consistency with what was built; note what must change in implementation."
    ),
    "architect-spec-task": "Produce a concise technical specification for the task.",
    "coder-implement": "Implement based on this specification:\n{spec}",
    "reviewer-review": (
        "Review the specification and implementation.\n"
        "Spec:\n{spec}\n\nCode:\n{code}"
    ),
    "deployer-summarize": (
        "Summarize deployment steps: docker compose service, exposed port, health check."
    ),
    "tester-recovery-extra": (
        "You diagnose failures in an autonomous dev pipeline. "
        "Never ask the user to fix bugs — pick an automated action. "
        "Prefer retry_deploy for Docker/compose issues and fix_code for app errors. "
        "Use escalate only when attempts are exhausted or the issue is ambiguous."
    ),
    "supervisor-route": (
        "Reply with exactly one worker name to invoke next, or 'finish' if done."
    ),
}

# The live catalogue is loaded by /api/team/models; keep saved selections offline.
SUGGESTED_MODELS: list[str] = []


class TeamConfigManager:
    """Filesystem-backed agent prompts and model configuration."""

    def __init__(self, root: Path | None = None) -> None:
        config = get_config()
        self.root = root or (config.governance_dir / "agents")
        self.defaults_dir = self.root / "defaults"
        self.prompts_dir = self.root / "prompts"
        self.workflows_defaults_dir = self.defaults_dir / "workflows"
        self.workflows_prompts_dir = self.prompts_dir / "workflows"
        self.config_path = self.root / "team_config.json"
        self.ensure_layout()

    def ensure_layout(self) -> None:
        self.defaults_dir.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.workflows_defaults_dir.mkdir(parents=True, exist_ok=True)
        self.workflows_prompts_dir.mkdir(parents=True, exist_ok=True)

        for role in AgentRole:
            default_file = self.defaults_dir / f"{role.value}.md"
            if not default_file.exists():
                default_file.write_text(ROLE_DEFAULT_PROMPTS[role].strip() + "\n", encoding="utf-8")
            prompt_file = self.prompts_dir / f"{role.value}.md"
            if not prompt_file.exists():
                shutil.copy2(default_file, prompt_file)

        for name in WORKFLOW_PROMPT_NAMES:
            default_wf = self.workflows_defaults_dir / f"{name}.md"
            if not default_wf.exists():
                default_wf.write_text(WORKFLOW_DEFAULT_PROMPTS[name].strip() + "\n", encoding="utf-8")
            prompt_wf = self.workflows_prompts_dir / f"{name}.md"
            if not prompt_wf.exists():
                shutil.copy2(default_wf, prompt_wf)

        if not self.config_path.exists():
            self._write_config({role.value: DEFAULT_MODELS[role] for role in AgentRole})

    def _read_config(self) -> dict[str, str]:
        if not self.config_path.exists():
            return {role.value: DEFAULT_MODELS[role] for role in AgentRole}
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        models = data.get("models", {})
        result = {role.value: DEFAULT_MODELS[role] for role in AgentRole}
        for role in AgentRole:
            if role.value in models and str(models[role.value]).strip():
                result[role.value] = str(models[role.value]).strip()
        return result

    def _write_config(self, models: dict[str, str]) -> None:
        payload = {
            "models": models,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self.config_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def read_role_prompt(self, role: AgentRole) -> str:
        path = self.prompts_dir / f"{role.value}.md"
        return path.read_text(encoding="utf-8").strip()

    def read_role_default_prompt(self, role: AgentRole) -> str:
        path = self.defaults_dir / f"{role.value}.md"
        return path.read_text(encoding="utf-8").strip()

    def write_role_prompt(self, role: AgentRole, content: str) -> None:
        path = self.prompts_dir / f"{role.value}.md"
        path.write_text(content.rstrip() + "\n", encoding="utf-8")

    def read_workflow_prompt(self, name: str) -> str:
        path = self.workflows_prompts_dir / f"{name}.md"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        return WORKFLOW_DEFAULT_PROMPTS.get(name, "").strip()

    def read_workflow_default_prompt(self, name: str) -> str:
        path = self.workflows_defaults_dir / f"{name}.md"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        return WORKFLOW_DEFAULT_PROMPTS.get(name, "").strip()

    def write_workflow_prompt(self, name: str, content: str) -> None:
        path = self.workflows_prompts_dir / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")

    def get_model(self, role: AgentRole) -> str:
        return self._read_config()[role.value]

    def set_model(self, role: AgentRole, model: str) -> None:
        models = self._read_config()
        models[role.value] = model.strip()
        self._write_config(models)

    def reset_to_defaults(self) -> None:
        if self.defaults_dir.exists():
            for role in AgentRole:
                src = self.defaults_dir / f"{role.value}.md"
                dst = self.prompts_dir / f"{role.value}.md"
                if src.exists():
                    shutil.copy2(src, dst)
        if self.workflows_defaults_dir.exists():
            for path in self.workflows_defaults_dir.glob("*.md"):
                shutil.copy2(path, self.workflows_prompts_dir / path.name)
        self._write_config({role.value: DEFAULT_MODELS[role] for role in AgentRole})

    def is_role_customized(self, role: AgentRole) -> bool:
        current = self.read_role_prompt(role)
        default = self.read_role_default_prompt(role)
        model_custom = self.get_model(role) != DEFAULT_MODELS[role]
        return current != default or model_custom

    def build_team(self) -> AgentTeam:
        models = self._read_config()
        overrides = {role: models[role.value] for role in AgentRole}
        team = AgentTeam.default(models=overrides)
        agents = dict(team.agents)
        for role in AgentRole:
            cfg = agents[role]
            agents[role] = type(cfg)(
                role=cfg.role,
                name=cfg.name,
                model=cfg.model,
                system_prompt=self.read_role_prompt(role),
                description=cfg.description,
            )
        return AgentTeam(agents=agents)

    def list_agents_config(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for role in AgentRole:
            items.append(
                {
                    "role": role.value,
                    "name": role.value.capitalize(),
                    "description": ROLE_DESCRIPTIONS[role],
                    "model": self.get_model(role),
                    "default_model": DEFAULT_MODELS[role],
                    "prompt": self.read_role_prompt(role),
                    "default_prompt": self.read_role_default_prompt(role),
                    "prompt_path": str(self.prompts_dir / f"{role.value}.md"),
                    "customized": self.is_role_customized(role),
                }
            )
        return items

    def list_workflow_prompts(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for name in WORKFLOW_PROMPT_NAMES:
            current = self.read_workflow_prompt(name)
            default = self.read_workflow_default_prompt(name)
            items.append(
                {
                    "name": name,
                    "prompt": current,
                    "default_prompt": default,
                    "prompt_path": str(self.workflows_prompts_dir / f"{name}.md"),
                    "customized": current != default,
                }
            )
        return items


_team_manager: TeamConfigManager | None = None


def get_team_manager() -> TeamConfigManager:
    global _team_manager
    if _team_manager is None:
        _team_manager = TeamConfigManager()
    return _team_manager


def load_agent_team() -> AgentTeam:
    return get_team_manager().build_team()


def get_workflow_prompt(name: str, **kwargs: str) -> str:
    """Load workflow instruction markdown and apply optional format placeholders."""
    text = get_team_manager().read_workflow_prompt(name)
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text