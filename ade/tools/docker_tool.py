"""Docker container management for ADI isolation."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field

from ade.core.config import get_config

logger = logging.getLogger(__name__)


class DockerToolError(RuntimeError):
    """Raised when a docker CLI command fails."""


@dataclass
class ContainerSpec:
    """Specification for running an isolated ADI container."""

    image: str
    name: str
    command: list[str] | None = None
    env: dict[str, str] = field(default_factory=dict)
    ports: dict[str, str] = field(default_factory=dict)
    volumes: dict[str, str] = field(default_factory=dict)
    network: str | None = None
    detach: bool = True
    remove: bool = False


class DockerTool:
    """Basic Docker wrapper for future ADI workspace isolation."""

    def __init__(self, network_prefix: str | None = None) -> None:
        config = get_config()
        self.network_prefix = network_prefix or config.docker_network_prefix
        self.socket = config.docker_socket

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        cmd = ["docker", *args]
        logger.debug("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            raise DockerToolError(f"docker {' '.join(args)} failed: {stderr}")
        return result

    def is_available(self) -> bool:
        try:
            self._run("info", "--format", "{{.ServerVersion}}")
            return True
        except DockerToolError:
            return False

    def network_name(self, project_id: str) -> str:
        safe_id = project_id.lower().replace(" ", "-")
        return f"{self.network_prefix}-{safe_id}"

    def create_network(self, project_id: str) -> str:
        name = self.network_name(project_id)
        exists = self._run("network", "ls", "--format", "{{.Name}}", check=False)
        if name not in exists.stdout.splitlines():
            self._run("network", "create", name)
            logger.info("Created network %s", name)
        return name

    def remove_network(self, project_id: str) -> None:
        name = self.network_name(project_id)
        self._run("network", "rm", name, check=False)

    def run_container(self, spec: ContainerSpec) -> str:
        args: list[str] = ["run"]
        if spec.detach:
            args.append("-d")
        if spec.remove:
            args.append("--rm")
        args.extend(["--name", spec.name])

        for key, value in spec.env.items():
            args.extend(["-e", f"{key}={value}"])
        for host_port, container_port in spec.ports.items():
            args.extend(["-p", f"{host_port}:{container_port}"])
        for host_path, container_path in spec.volumes.items():
            args.extend(["-v", f"{host_path}:{container_path}"])
        if spec.network:
            args.extend(["--network", spec.network])

        args.append(spec.image)
        if spec.command:
            args.extend(spec.command)

        result = self._run(*args)
        container_id = result.stdout.strip()
        logger.info("Started container %s (%s)", spec.name, container_id[:12])
        return container_id

    def stop_container(self, name: str, *, timeout: int = 10) -> None:
        self._run("stop", "--time", str(timeout), name, check=False)

    def remove_container(self, name: str, *, force: bool = False) -> None:
        args = ["rm"]
        if force:
            args.append("-f")
        args.append(name)
        self._run(*args, check=False)

    def inspect_container(self, name: str) -> dict:
        result = self._run("inspect", name)
        data = json.loads(result.stdout)
        return data[0] if data else {}

    def list_project_containers(self, project_id: str) -> list[str]:
        prefix = f"{self.network_prefix}-{project_id}"
        result = self._run(
            "ps", "-a", "--filter", f"name={prefix}", "--format", "{{.Names}}"
        )
        return [line for line in result.stdout.splitlines() if line]
