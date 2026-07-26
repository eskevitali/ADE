"""Parse specification / TZ markdown into editable sections."""

from __future__ import annotations

import re
from typing import Any


def _slug(title: str, index: int) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or f"section-{index}"


def parse_sections(markdown: str) -> list[dict[str, Any]]:
    """Split markdown by ## headings into reviewable sections."""
    if not markdown.strip():
        return []

    sections: list[dict[str, Any]] = []
    current_title = "Введение"
    current_lines: list[str] = []
    index = 0

    for line in markdown.splitlines():
        if line.startswith("## "):
            if current_lines or index == 0:
                sections.append(
                    {
                        "id": _slug(current_title, index),
                        "title": current_title,
                        "content": "\n".join(current_lines).strip(),
                    }
                )
                index += 1
            current_title = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    sections.append(
        {
            "id": _slug(current_title, index),
            "title": current_title,
            "content": "\n".join(current_lines).strip(),
        }
    )

    return [s for s in sections if s["content"] or s["title"] != "Введение" or len(sections) == 1]


def rebuild_markdown(sections: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for section in sections:
        title = section.get("title", "Section")
        content = section.get("content", "").strip()
        if title == "Введение" and not content:
            continue
        if title == "Введение":
            parts.append(content)
        else:
            parts.append(f"## {title}\n\n{content}")
    return "\n\n".join(parts).strip() + "\n"


def replace_section(markdown: str, section_id: str, new_content: str) -> str:
    sections = parse_sections(markdown)
    for section in sections:
        if section["id"] == section_id:
            section["content"] = new_content.strip()
            break
    return rebuild_markdown(sections)