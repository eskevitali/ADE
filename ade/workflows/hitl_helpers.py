"""LLM helpers for human-in-the-loop discussion and document revision."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ade.core.agent_team import AgentRole, AgentTeam
from ade.core.llm_provider import get_llm
from ade.core.policy_context import organizational_context
from ade.core.team_config import get_workflow_prompt
from ade.core.spec_parser import parse_sections, replace_section


def _architect(team: AgentTeam, system: str, messages: list) -> str:
    config = team.get(AgentRole.ARCHITECT)
    llm = get_llm(config.model)
    system += "\n\n" + organizational_context(str(messages[-1].content) if messages else "")
    response = llm.invoke([SystemMessage(content=system), *messages])
    content = response.content if isinstance(response.content, str) else str(response.content)
    return content


def discuss_idea(team: AgentTeam, idea: str, history: list[dict[str, str]], user_message: str) -> str:
    system = (
        f"{team.get(AgentRole.ARCHITECT).system_prompt}\n\n"
        f"{get_workflow_prompt('architect-discuss-idea', idea=idea)}"
    )
    messages: list = [HumanMessage(content=f"Original idea: {idea}")]
    for item in history:
        if item["role"] == "user":
            messages.append(HumanMessage(content=item["content"]))
        else:
            messages.append(AIMessage(content=item["content"], name="Architect"))
    messages.append(HumanMessage(content=user_message))
    return _architect(team, system, messages)


def generate_tz(team: AgentTeam, idea: str, discussion: list[dict[str, str]]) -> str:
    discussion_text = "\n".join(
        f"{m['role']}: {m['content']}" for m in discussion[-20:]
    )
    system = (
        f"{team.get(AgentRole.ARCHITECT).system_prompt}\n\n"
        f"{get_workflow_prompt('architect-generate-tz')}"
    )
    prompt = f"Idea:\n{idea}\n\nDiscussion:\n{discussion_text or '(no discussion)'}"
    return _architect(team, system, [HumanMessage(content=prompt)])


def generate_spec_from_tz(team: AgentTeam, idea: str, tz: str) -> str:
    system = (
        f"{team.get(AgentRole.ARCHITECT).system_prompt}\n\n"
        f"{get_workflow_prompt('architect-generate-spec')}"
    )
    prompt = f"Idea:\n{idea}\n\nApproved ТЗ:\n{tz}"
    return _architect(team, system, [HumanMessage(content=prompt)])


def revise_document_section(
    team: AgentTeam,
    doc_type: str,
    document: str,
    section_id: str,
    user_comment: str,
    idea: str = "",
) -> tuple[str, dict[str, Any] | None]:
    sections = parse_sections(document)
    target = next((s for s in sections if s["id"] == section_id), None)
    if not target:
        return document, None

    system = (
        f"{team.get(AgentRole.ARCHITECT).system_prompt}\n\n"
        f"{get_workflow_prompt('architect-revise-section', doc_type=doc_type)}"
    )
    prompt = (
        f"Project idea: {idea}\n\n"
        f"Section title: {target['title']}\n"
        f"Current content:\n{target['content']}\n\n"
        f"User feedback:\n{user_comment}"
    )
    revised_body = _architect(team, system, [HumanMessage(content=prompt)])
    updated = replace_section(document, section_id, revised_body)
    for section in parse_sections(updated):
        if section["id"] == section_id:
            return updated, section
    return updated, None


def revise_tz_and_spec_from_feedback(
    team: AgentTeam,
    idea: str,
    tz: str,
    spec: str,
    review: str,
    feedback: str,
) -> tuple[str, str]:
    """Update ТЗ and Spec after user reflection / revise request."""
    tz_system = (
        f"{team.get(AgentRole.ARCHITECT).system_prompt}\n\n"
        f"{get_workflow_prompt('architect-revise-tz')}"
    )
    tz_prompt = (
        f"Idea:\n{idea}\n\nCurrent ТЗ:\n{tz}\n\nReview summary:\n{review[:2000]}\n\n"
        f"User reflection / revision request:\n{feedback}"
    )
    new_tz = _architect(team, tz_system, [HumanMessage(content=tz_prompt)])

    spec_system = (
        f"{team.get(AgentRole.ARCHITECT).system_prompt}\n\n"
        f"{get_workflow_prompt('architect-revise-spec')}"
    )
    spec_prompt = (
        f"Idea:\n{idea}\n\nRevised ТЗ:\n{new_tz}\n\nPrevious Spec:\n{spec}\n\n"
        f"User feedback:\n{feedback}"
    )
    new_spec = _architect(team, spec_system, [HumanMessage(content=spec_prompt)])
    return new_tz, new_spec