"""Safe docker compose invocation with plugin + legacy fallback."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def run_compose(
    project_path: Path,
    *args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run docker compose; never raises FileNotFoundError."""
    compose = project_path / "docker-compose.yml"
    workdir = cwd or project_path
    commands = (
        ["docker", "compose", "-f", str(compose), *args],
        ["docker-compose", "-f", str(compose), *args],
    )
    last: subprocess.CompletedProcess[str] | None = None
    missing: list[str] = []

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                cwd=str(workdir),
            )
            if result.returncode == 0:
                return result
            last = result
        except FileNotFoundError:
            missing.append(cmd[0] if cmd[0] != "docker" else "docker compose")
            continue

    if last is not None:
        return last

    hint = "Установите docker compose plugin в backend-контейнере"
    if missing:
        hint = f"Не найдены: {', '.join(missing)}. {hint}"
    logger.error("Compose unavailable in %s", workdir)
    return subprocess.CompletedProcess(
        args=["docker", "compose"],
        returncode=127,
        stdout="",
        stderr=hint,
    )