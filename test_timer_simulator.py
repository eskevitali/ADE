#!/usr/bin/env python3
"""Tests for interactive timer simulator deliverable."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from ade.core.adi_manager import ADIManager
from ade.core.deliverable import (
    build_deliverable,
    detect_project_type,
    ensure_timer_simulator,
    needs_interactive_simulator,
)
from ade.core.deployer import DeployerService


def test_detect_simulator_type() -> None:
    spec = "интерактивный симулятор таймера с переменными"
    assert detect_project_type("demo", spec) == "simulator"
    assert needs_interactive_simulator("demo", spec)
    print("[OK] detect simulator type")


def test_ensure_timer_simulator_scaffold() -> None:
    adi = ADIManager()
    project_id = f"sim-{uuid.uuid4().hex[:8]}"
    adi.bootstrap(project_id, "Timer Demo", "timer", enable_isolation=False)
    path = adi.project_path(project_id)
    (path / "src" / "main.py").write_text("Hello, World!\n", encoding="utf-8")

    ensure_timer_simulator(path, "Timer Demo", "симулятор таймера")
    assert (path / "preview" / "timer-simulator.html").exists()
    main = (path / "src" / "main.py").read_text(encoding="utf-8")
    assert "class TimerSimulator" in main
    compile(main, "main.py", "exec")

    deliverable = build_deliverable(project_id, "Timer Demo", "timer", "симулятор", main, path)
    assert deliverable["type"] == "simulator"
    assert deliverable["preview_url"].endswith("/simulator")
    print("[OK] ensure_timer_simulator scaffold")


def test_deployer_simulator_preview_mode() -> None:
    adi = ADIManager()
    project_id = f"sim-{uuid.uuid4().hex[:8]}"
    adi.bootstrap(project_id, "Timer Deploy", "timer", enable_isolation=False)
    path = adi.project_path(project_id)
    ensure_timer_simulator(path, "Timer Deploy", "симулятор таймера")

    svc = DeployerService(adi_manager=adi)
    cmd, port, mode = svc._detect_start_command(path)
    assert mode == "simulator_preview"
    assert port == 8080

    url, label = svc._user_facing_url(project_id, path, mode=mode, host_port=8080, running=True)
    assert "/simulator" in url
    assert "симулятор" in label.lower()
    print("[OK] deployer simulator_preview mode")


def main() -> int:
    print("=== Timer simulator tests ===\n")
    try:
        test_detect_simulator_type()
        test_ensure_timer_simulator_scaffold()
        test_deployer_simulator_preview_mode()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        raise
    print("\n=== All timer simulator tests passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())