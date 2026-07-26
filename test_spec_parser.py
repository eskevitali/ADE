#!/usr/bin/env python3
"""Tests for spec section parser."""

from __future__ import annotations

import sys

from ade.core.deliverable import detect_project_type
from ade.core.spec_parser import parse_sections, rebuild_markdown, replace_section


def test_parse_sections() -> None:
    md = "## Цели\n\nBuild app\n\n## API\n\nREST endpoints"
    sections = parse_sections(md)
    assert len(sections) == 2
    assert sections[0]["title"] == "Цели"
    print("[OK] parse_sections")


def test_replace_section() -> None:
    md = "## Цели\n\nOld\n\n## API\n\nKeep"
    updated = replace_section(md, parse_sections(md)[0]["id"], "New goals")
    assert "New goals" in updated
    assert "Keep" in updated
    print("[OK] replace_section")


def test_detect_mobile() -> None:
    assert detect_project_type("iOS Android GPS app", "", "") == "mobile"
    assert detect_project_type("FastAPI web dashboard", "", "") == "web"
    print("[OK] detect_project_type")


def main() -> int:
    print("=== Spec parser tests ===\n")
    try:
        test_parse_sections()
        test_replace_section()
        test_detect_mobile()
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print("\n=== All passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())