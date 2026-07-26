#!/usr/bin/env python3
"""
E2E simulation: Я ТУТ v3 — one user action per step (no improvement loops).
Hits live backend over HTTP so background workflows run correctly.
"""

from __future__ import annotations

import sys
import time
from typing import Any

import httpx

from ade.core.adi_manager import ADIManager
from ade.core.config import get_config

BASE = "http://127.0.0.1:8000"

IDEA = (
    "Я ТУТ v3 — утилитарное мобильное приложение (iOS/Android) для мгновенного захвата "
    "GPS-координат устройства и отправки их выбранному контакту в один клик. "
    "Контакт и способ отправки (SMS/WhatsApp/Telegram) задаются в настройках. "
    "Главный экран минималистичный: одна крупная кнопка «Я ТУТ» и иконка настроек."
)
DISCUSS_MSG = (
    "Уточнение: на главном экране только кнопка «Я ТУТ», без текста координат и без Spec. "
    "Настройки контакта и способа отправки — в выпадающем меню по иконке шестерёнки."
)
REVISE_FEEDBACK = (
    "После теста: сделать кнопку «Я ТУТ» на 20% крупнее и ярче (фиолетовый градиент). "
    "В меню настроек добавить пункт «Способ отправки: SMS по умолчанию»."
)

POLL_SEC = 4
GATE_TIMEOUT = 900
REBUILD_TIMEOUT = 900


def log(step: str, detail: str = "") -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {step}" + (f" — {detail}" if detail else ""), flush=True)


def login(client: httpx.Client) -> None:
    config = get_config()
    res = client.post(
        f"{BASE}/auth/login",
        data={"username": config.admin_username, "password": config.admin_password},
        follow_redirects=True,
    )
    res.raise_for_status()
    log("LOGIN", "ok")


def wait_task(client: httpx.Client, task_id: str, *, want_gate: str = "", want_status: str = "", timeout: int = GATE_TIMEOUT) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = client.get(f"{BASE}/api/tasks/{task_id}")
        data = res.json()
        if data.get("status") != "ok":
            time.sleep(POLL_SEC)
            continue
        gate = data.get("pending_gate") or ""
        status = data.get("workflow_status") or ""
        phase = data.get("phase") or ""
        if want_gate and gate == want_gate:
            return data
        if want_status and status == want_status:
            return data
        if status == "failed":
            raise RuntimeError(f"Task failed: {data.get('error')}")
        if want_gate and not gate and status == "running":
            log("WAIT", f"running phase={phase} (ожидаем gate={want_gate})")
        time.sleep(POLL_SEC)
    raise TimeoutError(f"Timeout waiting gate={want_gate!r} status={want_status!r} task={task_id}")


def wait_rebuild(client: httpx.Client, project_id: str, timeout: int = REBUILD_TIMEOUT) -> dict[str, Any]:
    deadline = time.time() + timeout
    last_phase = ""
    while time.time() < deadline:
        res = client.get(f"{BASE}/api/projects/{project_id}/rebuild-status")
        data = res.json()
        assert data.get("status") == "ok", data
        phase = data.get("rebuild_phase") or data.get("rebuild_status") or ""
        if phase != last_phase:
            log("REBUILD", phase)
            last_phase = phase
        if data.get("rebuild_status") == "completed":
            return data
        if data.get("rebuild_status") == "failed":
            raise RuntimeError(f"Rebuild failed: {data}")
        time.sleep(POLL_SEC)
    raise TimeoutError(f"Rebuild timeout for {project_id}")


def main() -> int:
    print("=== E2E: Я ТУТ v3 (one click per step) ===\n", flush=True)
    adi = ADIManager()

    with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        login(client)

        log("STEP 1", "Create project")
        res = client.post(
            f"{BASE}/api/tasks",
            json={
                "task": IDEA,
                "project_name": "Я ТУТ v3",
                "workflow": "dev_cycle",
                "human_in_loop": True,
            },
        )
        res.raise_for_status()
        task_id = res.json()["task_id"]
        task_data = wait_task(client, task_id, want_gate="idea")
        project_id = task_data["project_id"]
        log("PROJECT", project_id)

        log("STEP 2", "Discuss (1 message)")
        dres = client.post(f"{BASE}/api/tasks/{task_id}/discuss", json={"message": DISCUSS_MSG})
        assert dres.json().get("status") == "ok", dres.json()

        log("STEP 3", "Approve idea")
        client.post(f"{BASE}/api/tasks/{task_id}/approve", json={"gate": "idea"})
        wait_task(client, task_id, want_gate="tz")

        log("STEP 4", "Approve TZ")
        client.post(f"{BASE}/api/tasks/{task_id}/approve", json={"gate": "tz"})
        wait_task(client, task_id, want_gate="spec")

        log("STEP 5", "Approve Spec")
        client.post(f"{BASE}/api/tasks/{task_id}/approve", json={"gate": "spec"})
        wait_task(client, task_id, want_gate="code")

        log("STEP 6", "Approve Code")
        client.post(f"{BASE}/api/tasks/{task_id}/approve", json={"gate": "code"})
        wait_task(client, task_id, want_status="completed")

    project = adi.get_project(project_id)
    assert project and project.status == "completed", project
    log("WORKFLOW", "completed")

    with httpx.Client(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        login(client)

        log("STEP 7", "Revise (1 iteration)")
        rres = client.post(f"{BASE}/api/projects/{project_id}/revise", json={"feedback": REVISE_FEEDBACK})
        rdata = rres.json()
        assert rdata.get("status") == "ok", rdata
        rev_id = rdata["revision_id"]
        log("REVISION", f"rev-{rev_id}")

        log("STEP 8", "Confirm revision")
        cres = client.post(f"{BASE}/api/projects/{project_id}/revision/{rev_id}/confirm")
        assert cres.json().get("status") == "ok", cres.json()

        log("STEP 9", "Wait rebuild pipeline")
        rb = wait_rebuild(client, project_id)
        log("DEPLOY", rb.get("deploy_status", "?"))

        log("STEP 10", "Accept project")
        ares = client.post(f"{BASE}/api/projects/{project_id}/accept")
        assert ares.json().get("status") == "ok", ares.json()

    mockup = adi.project_path(project_id) / "preview" / "mobile-mockup.html"
    assert mockup.exists(), "mockup missing"
    html = mockup.read_text(encoding="utf-8")
    assert "Я ТУТ" in html
    assert "Техническая спецификация" not in html

    print(f"\n=== E2E PASSED ===\nProject: {project_id}\nTask: {task_id}\nPreview: {BASE}/preview/{project_id}/mobile")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n[E2E FAIL] {exc}", file=sys.stderr)
        raise