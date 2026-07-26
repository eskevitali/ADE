"""Resolve container paths to host paths for Docker bind mounts."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_docker_bind_source(path: Path) -> Path:
    """
    Map a path inside the backend container to the host path Docker expects.

    When ADE runs in Docker and invokes `docker compose` via the mounted socket,
    relative volume entries are resolved on the host — so `./src` becomes `/app/...`
    instead of `/root/ADE-V4/projects/...`. Use this before writing compose files.
    """
    resolved = path.resolve()
    host_override = os.environ.get("ADE_PROJECTS_HOST_DIR", "").strip()
    if host_override and str(resolved).startswith("/app/projects/"):
        rel = resolved.relative_to("/app/projects")
        return (Path(host_override) / rel).resolve()

    mapped = _map_via_mountinfo(resolved)
    return mapped if mapped is not None else resolved


def _map_via_mountinfo(path: Path) -> Path | None:
    path_s = str(path)
    mappings: list[tuple[str, Path]] = []
    try:
        with open("/proc/self/mountinfo", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 10:
                    continue
                host_root = Path(parts[3])
                mount_point = parts[4]
                if mount_point == "/" or host_root == Path("/"):
                    continue
                mappings.append((mount_point, host_root))
    except OSError:
        return None

    mappings.sort(key=lambda item: len(item[0]), reverse=True)
    for mount_point, host_root in mappings:
        if path_s == mount_point or path_s.startswith(mount_point + "/"):
            rel = path_s[len(mount_point) :].lstrip("/")
            return host_root / rel if rel else host_root
    return None