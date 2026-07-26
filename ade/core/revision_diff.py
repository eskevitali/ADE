"""Compare document revisions and produce highlighted section diffs."""

from __future__ import annotations

import difflib
import html
from typing import Any

from ade.core.spec_parser import parse_sections


def _line_diff_html(old: str, new: str) -> str:
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    parts: list[str] = []
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in new_lines[j1:j2]:
                parts.append(f'<div class="text-gray-400">{html.escape(line)}</div>')
        elif tag == "insert":
            for line in new_lines[j1:j2]:
                parts.append(
                    f'<div class="bg-emerald-900/50 text-emerald-200 px-2 py-0.5 rounded my-0.5 border-l-2 border-emerald-500">'
                    f"+ {html.escape(line)}</div>"
                )
        elif tag == "delete":
            for line in old_lines[i1:i2]:
                parts.append(
                    f'<div class="bg-red-900/40 text-red-300/90 px-2 py-0.5 rounded my-0.5 border-l-2 border-red-500 line-through">'
                    f"− {html.escape(line)}</div>"
                )
        elif tag == "replace":
            for line in old_lines[i1:i2]:
                parts.append(
                    f'<div class="bg-red-900/40 text-red-300/90 px-2 py-0.5 rounded my-0.5 border-l-2 border-red-500 line-through">'
                    f"− {html.escape(line)}</div>"
                )
            for line in new_lines[j1:j2]:
                parts.append(
                    f'<div class="bg-emerald-900/50 text-emerald-200 px-2 py-0.5 rounded my-0.5 border-l-2 border-emerald-500">'
                    f"+ {html.escape(line)}</div>"
                )
    return "\n".join(parts) if parts else f'<div class="text-gray-400">{html.escape(new)}</div>'


def compare_sections(old_md: str, new_md: str) -> list[dict[str, Any]]:
    old_map = {s["id"]: s for s in parse_sections(old_md)}
    new_list = parse_sections(new_md)
    new_ids = {s["id"] for s in new_list}
    sections: list[dict[str, Any]] = []

    for section in new_list:
        old = old_map.get(section["id"])
        entry: dict[str, Any] = {
            "id": section["id"],
            "title": section["title"],
            "content": section["content"],
        }
        if not old:
            entry["change"] = "added"
            entry["diff_html"] = (
                f'<div class="bg-emerald-900/50 text-emerald-200 px-2 py-1 rounded border-l-2 border-emerald-500">'
                f"{html.escape(section['content'])}</div>"
            )
        elif old["content"].strip() != section["content"].strip():
            entry["change"] = "modified"
            entry["old_content"] = old["content"]
            entry["diff_html"] = _line_diff_html(old["content"], section["content"])
        else:
            entry["change"] = "unchanged"
            entry["diff_html"] = f'<div class="text-gray-400">{html.escape(section["content"])}</div>'
        sections.append(entry)

    for sid, old in old_map.items():
        if sid not in new_ids:
            sections.append(
                {
                    "id": sid,
                    "title": old["title"],
                    "content": old["content"],
                    "change": "removed",
                    "diff_html": (
                        f'<div class="bg-red-900/40 text-red-300 px-2 py-1 rounded border-l-2 border-red-500 line-through">'
                        f"{html.escape(old['content'])}</div>"
                    ),
                }
            )
    return sections


def summarize_changes(tz_sections: list[dict], spec_sections: list[dict]) -> dict[str, int]:
    all_sections = tz_sections + spec_sections
    return {
        "modified": sum(1 for s in all_sections if s["change"] == "modified"),
        "added": sum(1 for s in all_sections if s["change"] == "added"),
        "removed": sum(1 for s in all_sections if s["change"] == "removed"),
        "unchanged": sum(1 for s in all_sections if s["change"] == "unchanged"),
    }