"""Tester-driven recovery loop for deploy/rebuild failures."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ade.core.agent_team import AgentRole, AgentTeam
from ade.core.llm_provider import get_llm
from ade.core.team_config import get_workflow_prompt

logger = logging.getLogger(__name__)

JSON_BLOCK_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


class RecoveryAction(str, Enum):
    RETRY_DEPLOY = "retry_deploy"
    FIX_CODE = "fix_code"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class FailureContext:
    failure_type: str
    phase: str
    error: str
    attempt: int
    max_attempts: int
    spec: str = ""
    code: str = ""
    deploy_error: str = ""


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    reason: str
    fix_hint: str = ""


def classify_failure_heuristic(ctx: FailureContext) -> RecoveryDecision | None:
    """Fast rule-based routing when the error pattern is unambiguous."""
    err = (ctx.error + "\n" + ctx.deploy_error).lower()
    if not err:
        return None

    infra_markers = (
        "empty compose",
        "compose file",
        "docker daemon",
        "connection refused",
        "network",
        "port is already allocated",
        "cannot connect to the docker",
    )
    if any(marker in err for marker in infra_markers):
        return RecoveryDecision(
            action=RecoveryAction.RETRY_DEPLOY,
            reason="Инфраструктурная ошибка деплоя — повтор без правки кода",
        )

    code_markers = (
        "syntaxerror",
        "syntax error",
        "indentationerror",
        "modulenotfounderror",
        "importerror",
        "nameerror",
        "invalid syntax",
        "traceback",
        "exit code 1",
    )
    if any(marker in err for marker in code_markers):
        return RecoveryDecision(
            action=RecoveryAction.FIX_CODE,
            reason="Ошибка выполнения/синтаксиса — нужна правка кода",
            fix_hint=ctx.error[:800],
        )

    return None


def _parse_tester_json(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = JSON_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def analyze_failure_with_tester(team: AgentTeam, ctx: FailureContext) -> RecoveryDecision:
    """Ask Tester LLM for the next recovery step."""
    heuristic = classify_failure_heuristic(ctx)
    if heuristic:
        return heuristic

    config = team.get(AgentRole.TESTER)
    prompt = (
        f"Failure type: {ctx.failure_type}\n"
        f"Phase: {ctx.phase}\n"
        f"Attempt: {ctx.attempt}/{ctx.max_attempts}\n"
        f"Error:\n{ctx.error[:1500]}\n\n"
        f"Spec excerpt:\n{ctx.spec[:1200]}\n\n"
        f"Code excerpt:\n{ctx.code[:1200]}\n\n"
        "Choose exactly one action:\n"
        '- "retry_deploy" — infrastructure/compose issue, code likely fine\n'
        '- "fix_code" — application bug, invalid code, or runtime error\n'
        '- "escalate" — unrecoverable or needs human (use if attempt is last)\n\n'
        'Reply with JSON only: {"action":"...", "reason":"...", "fix_hint":"..."}'
    )
    try:
        llm = get_llm(config.model)
        response = llm.invoke(
            [
                SystemMessage(
                    content=(
                        f"{config.system_prompt}\n\n"
                        f"{get_workflow_prompt('tester-recovery-extra')}"
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )
        raw = response.content if isinstance(response.content, str) else str(response.content)
        parsed = _parse_tester_json(raw)
        if parsed:
            action_raw = str(parsed.get("action", "")).strip().lower()
            action = RecoveryAction(action_raw) if action_raw in RecoveryAction._value2member_map_ else RecoveryAction.FIX_CODE
            return RecoveryDecision(
                action=action,
                reason=str(parsed.get("reason", "Tester analysis"))[:500],
                fix_hint=str(parsed.get("fix_hint", ""))[:800],
            )
    except Exception as exc:
        logger.warning("Tester recovery analysis failed: %s", exc)

    if ctx.attempt >= ctx.max_attempts:
        return RecoveryDecision(
            action=RecoveryAction.ESCALATE,
            reason="Лимит попыток исчерпан, эвристика не определила действие",
        )
    return RecoveryDecision(
        action=RecoveryAction.FIX_CODE,
        reason="Не удалось классифицировать — пробуем правку кода",
        fix_hint=ctx.error[:500],
    )


class RecoveryService:
    """Coordinates Tester decisions and attempt limits."""

    def __init__(self, team: AgentTeam | None = None) -> None:
        self.team = team or AgentTeam.default()

    def decide(self, ctx: FailureContext) -> RecoveryDecision:
        if ctx.attempt >= ctx.max_attempts:
            return RecoveryDecision(
                action=RecoveryAction.ESCALATE,
                reason=f"Достигнут лимит автовосстановления ({ctx.max_attempts})",
            )
        decision = analyze_failure_with_tester(self.team, ctx)
        if ctx.attempt >= ctx.max_attempts and decision.action != RecoveryAction.ESCALATE:
            return RecoveryDecision(
                action=RecoveryAction.ESCALATE,
                reason=f"Лимит {ctx.max_attempts} попыток — эскалация вместо {decision.action.value}",
            )
        return decision