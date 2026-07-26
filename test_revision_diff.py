#!/usr/bin/env python3
"""Tests for revision diff highlighting."""

from __future__ import annotations

import sys

from ade.core.revision_diff import compare_sections, summarize_changes


def test_compare_modified_section() -> None:
    old = "## Цели\n\nСтарое\n\n## API\n\nБез изменений"
    new = "## Цели\n\nНовое\n\n## API\n\nБез изменений"
    sections = compare_sections(old, new)
    goals = next(s for s in sections if s["title"] == "Цели")
    api = next(s for s in sections if s["title"] == "API")
    assert goals["change"] == "modified"
    assert api["change"] == "unchanged"
    assert "Новое" in goals["diff_html"]
    assert "−" in goals["diff_html"] or "Старое" in goals["diff_html"]
    print("[OK] Modified section diff")


def test_summarize() -> None:
    sections = [
        {"change": "modified"},
        {"change": "added"},
        {"change": "unchanged"},
    ]
    s = summarize_changes(sections, [])
    assert s["modified"] == 1
    assert s["added"] == 1
    print("[OK] summarize_changes")


def main() -> int:
    print("=== Revision diff tests ===\n")
    try:
        test_compare_modified_section()
        test_summarize()
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print("\n=== All passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())