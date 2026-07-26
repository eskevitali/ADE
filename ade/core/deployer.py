"""Deployer agent and workspace deployment orchestration."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ade.core.agent_team import AgentRole, AgentTeam
from ade.core.team_config import get_workflow_prompt
from ade.core.adi_manager import ADIManager
from ade.core.config import get_config
from ade.core.llm_provider import get_llm
from ade.tools.compose_runner import run_compose
from ade.tools.docker_paths import resolve_docker_bind_source
from ade.tools.docker_tool import DockerTool

logger = logging.getLogger(__name__)

WORKSPACE_PORT_BASE = 18080
WORKSPACE_CONTAINER_PORTS: dict[str, int] = {
    "python_app": 8000,
    "web_static": 8080,
    "mobile_preview": 8080,
    "simulator_preview": 8080,
}


class DeployerService:
    """Deploy ADI workspace via docker compose and optional Deployer LLM."""

    def __init__(
        self,
        adi_manager: ADIManager | None = None,
        team: AgentTeam | None = None,
        docker_tool: DockerTool | None = None,
    ) -> None:
        self.adi = adi_manager or ADIManager()
        self.team = team or AgentTeam.default()
        self.docker = docker_tool or DockerTool()

    def _workspace_port(self, project_id: str) -> int:
        return WORKSPACE_PORT_BASE + (hash(project_id) % 900)

    _PYTHON_SERVER_MARKERS = (
        "uvicorn",
        "fastapi",
        "flask",
        "app.run(",
        "HTTPServer",
        "serve_forever",
        "http.server",
    )

    def _main_py_is_server(self, main_py: Path) -> bool:
        if not main_py.exists():
            return False
        try:
            content = main_py.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            return False
        return any(marker in content for marker in self._PYTHON_SERVER_MARKERS)

    def _detect_start_command(self, project_path: Path) -> tuple[str, int, str]:
        if (project_path / "preview" / "timer-simulator.html").exists():
            return "python -m http.server 8080", 8080, "simulator_preview"
        if (project_path / "preview" / "mobile-mockup.html").exists():
            return "python -m http.server 8080", 8080, "mobile_preview"
        src = project_path / "src"
        if (src / "index.html").exists() or (src / "app.html").exists():
            return "python -m http.server 8080", 8080, "web_static"
        if (src / "main.py").exists():
            if self._main_py_is_server(src / "main.py"):
                return "python src/main.py", 8000, "python_app"
            return (
                "sh -c 'python src/main.py; exec sleep infinity'",
                0,
                "python_script",
            )
        return "sleep infinity", 0, "idle"

    def _user_facing_url(
        self,
        project_id: str,
        project_path: Path,
        *,
        mode: str,
        host_port: int | None,
        running: bool,
    ) -> tuple[str, str]:
        """Public link the user can open in the browser (ADE preview, not localhost)."""
        sim = project_path / "preview" / "timer-simulator.html"
        if sim.exists():
            return f"/preview/{project_id}/simulator", "Открыть симулятор (браузер)"

        mockup = project_path / "preview" / "mobile-mockup.html"
        if mockup.exists():
            return f"/preview/{project_id}/mobile", "Симулятор макета (браузер)"

        src = project_path / "src"
        for name in ("index.html", "app.html", "main.html"):
            if (src / name).exists():
                return f"/preview/{project_id}", "Веб-превью"

        if running and mode in WORKSPACE_CONTAINER_PORTS:
            return f"/run/{project_id}/", "Открыть приложение"

        if running and mode == "python_script":
            return "", "Скрипт запущен (без веб-URL) — см. логи ниже"

        if running and mode == "idle":
            return "", "Контейнер запущен — HTTP-сервер не настроен"

        return "", ""

    def workspace_upstream(self, project_id: str) -> dict[str, str | int] | None:
        """Docker DNS target for reverse-proxying a running workspace HTTP server."""
        ws = self.get_workspace_status(project_id).get("workspace", {})
        if not ws.get("running"):
            return None
        mode = ws.get("mode", "")
        port = WORKSPACE_CONTAINER_PORTS.get(mode)
        if not port:
            return None
        return {
            "host": f"ade-adi-{project_id}-workspace",
            "port": port,
        }

    def _ensure_compose(self, project_id: str, project_name: str) -> Path:
        path = self.adi.project_path(project_id)
        compose_path = path / "docker-compose.yml"
        project = self.adi.get_project(project_id)
        network = project.network if project else ""
        port = self._workspace_port(project_id)
        cmd, container_port, mode = self._detect_start_command(path)

        proxy_network = get_config().workspace_proxy_network
        has_http_server = mode in WORKSPACE_CONTAINER_PORTS
        service_networks = ""
        networks_decl = ""
        if has_http_server:
            net_names = ["default", "ade_proxy"]
            if network:
                net_names.append("adi_net")
            service_networks = "    networks:\n" + "".join(
                f"      - {name}\n" for name in net_names
            )
            networks_decl = f"""
  ade_proxy:
    external: true
    name: {proxy_network}
"""
            if network:
                networks_decl += f"""  adi_net:
    external: true
    name: {network}
"""

        ports_block = ""
        service_cmd = "sleep infinity"
        workdir = "/workspace"
        host_path = resolve_docker_bind_source(path)
        src_mount = f"{host_path / 'src'}:/workspace/src"
        data_mount = f"{host_path / 'data'}:/workspace/data"
        extra_volumes = ""
        if mode in ("mobile_preview", "simulator_preview"):
            workdir = "/workspace/preview"
            service_cmd = "python -m http.server 8080"
            preview_mount = f"{host_path / 'preview'}:/workspace/preview"
            extra_volumes = f"      - {preview_mount}\n"
            ports_block = f"""
    ports:
      - "{port}:8080"
"""
        elif mode == "web_static":
            workdir = "/workspace/src"
            service_cmd = "python -m http.server 8080"
            ports_block = f"""
    ports:
      - "{port}:8080"
"""
        elif mode == "python_app":
            service_cmd = "python src/main.py"
            ports_block = f"""
    ports:
      - "{port}:8000"
"""
        elif mode == "python_script":
            service_cmd = "sh -c 'python src/main.py; exec sleep infinity'"

        compose_body = (
            f"# ADI workspace — {project_name}\n"
            f"# mode: {mode}\n"
            f"services:\n"
            f"  workspace:\n"
            f"    image: python:3.12-slim\n"
            f"    container_name: ade-adi-{project_id}-workspace\n"
            f"    working_dir: {workdir}\n"
            f"    volumes:\n"
            f"      - {src_mount}\n"
            f"      - {data_mount}\n"
            f"{extra_volumes}"
            f"    command: {service_cmd}\n"
            f"    restart: unless-stopped\n"
            f"{ports_block}"
            f"{service_networks}"
        )
        if networks_decl:
            compose_body += f"networks:{networks_decl}"
        compose_path.write_text(compose_body, encoding="utf-8")

        data = self.adi._read_manifest(project_id)
        if data:
            data["workspace_port"] = port if has_http_server else None
            data["workspace_mode"] = mode
            data["workspace_container_port"] = WORKSPACE_CONTAINER_PORTS.get(mode)
            self.adi._write_manifest(project_id, data)
        return compose_path

    def _invoke_deployer_agent(
        self,
        project_id: str,
        idea: str,
        spec: str,
        code: str,
    ) -> str:
        config = self.team.get(AgentRole.DEPLOYER)
        llm = get_llm(config.model)
        prompt = (
            f"Project ID: {project_id}\n"
            f"Idea: {idea[:500]}\n\n"
            f"Spec excerpt:\n{spec[:2000]}\n\n"
            f"Code excerpt:\n{code[:2000]}\n\n"
            f"{get_workflow_prompt('deployer-summarize')}"
        )
        try:
            response = llm.invoke(
                [SystemMessage(content=config.system_prompt), HumanMessage(content=prompt)]
            )
            content = response.content if isinstance(response.content, str) else str(response.content)
            return content[:4000]
        except Exception as exc:
            logger.warning("Deployer agent unavailable: %s", exc)
            return f"Deployer agent skipped: {exc}"

    def _compose_up(self, project_path: Path) -> subprocess.CompletedProcess[str]:
        return run_compose(project_path, "up", "-d", "--remove-orphans")

    def _container_logs(self, container_name: str, *, tail: int = 40) -> str:
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(tail), container_name],
                capture_output=True,
                text=True,
                check=False,
            )
            return (result.stdout + result.stderr).strip()[-4000:]
        except OSError:
            return ""

    def get_workspace_status(self, project_id: str) -> dict[str, Any]:
        project = self.adi.get_project(project_id)
        if not project:
            return {"status": "error", "message": "not_found"}

        container_name = f"ade-adi-{project_id}-workspace"
        running = False
        host_port: int | None = None
        state = "not_created"

        try:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    container_name,
                    "--format",
                    "{{.State.Status}}|{{range $p, $conf := .NetworkSettings.Ports}}{{if $conf}}{{(index $conf 0).HostPort}}{{end}}{{end}}",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split("|", 1)
                state = parts[0]
                running = state == "running"
                if len(parts) > 1 and parts[1].isdigit():
                    host_port = int(parts[1])
        except OSError:
            pass

        manifest = self.adi._read_manifest(project_id)
        workspace_port = manifest.get("workspace_port") or host_port
        project_path = self.adi.project_path(project_id)
        mode = manifest.get("workspace_mode", "idle")
        workspace_url, url_label = self._user_facing_url(
            project_id,
            project_path,
            mode=mode,
            host_port=workspace_port,
            running=running,
        )

        logs = self._container_logs(container_name) if state != "not_created" else ""

        return {
            "status": "ok",
            "project_id": project_id,
            "deploy_status": manifest.get("deploy_status", ""),
            "workspace": {
                "container": container_name,
                "state": state,
                "running": running,
                "network": project.network or "",
                "host_port": workspace_port,
                "url": workspace_url,
                "url_label": url_label,
                "mode": mode,
                "logs_tail": logs,
            },
        }

    def deploy(self, project_id: str, *, use_agent: bool = True) -> dict[str, Any]:
        project = self.adi.get_project(project_id)
        if not project:
            return {"status": "error", "message": "not_found"}

        if project.status == "rebuilding":
            return {"status": "error", "message": "rebuild_in_progress"}

        detail = self.adi.get_project_detail(project_id)
        spec = detail.get("spec", "") if detail else ""
        code = "\n".join(f["content"] for f in (detail or {}).get("src_files", []))

        deployer_notes = ""
        if use_agent and spec:
            deployer_notes = self._invoke_deployer_agent(
                project_id, project.idea, spec, code
            )
            notes_path = self.adi.project_path(project_id) / "review" / "DEPLOY.md"
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            notes_path.write_text(deployer_notes, encoding="utf-8")

        if project.isolation_enabled and not project.network:
            try:
                network = self.docker.create_network(project_id)
                data = self.adi._read_manifest(project_id)
                data["network"] = network
                data["isolation_enabled"] = True
                self.adi._write_manifest(project_id, data)
            except Exception as exc:
                logger.warning("Network create failed: %s", exc)

        self._ensure_compose(project_id, project.name)
        project_path = self.adi.project_path(project_id)
        result = self._compose_up(project_path)

        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            data = self.adi._read_manifest(project_id)
            data["deploy_status"] = "failed"
            data["deploy_error"] = stderr[:500]
            self.adi._write_manifest(project_id, data)
            return {
                "status": "error",
                "message": "deploy_failed",
                "detail": stderr[:500],
                "deployer_notes": deployer_notes[:500],
            }

        ws = self.get_workspace_status(project_id)
        data = self.adi._read_manifest(project_id)
        data["deploy_status"] = "running"
        data.pop("deploy_error", None)
        self.adi._write_manifest(project_id, data)

        return {
            "status": "ok",
            "message": "deployed",
            "deployer_notes": deployer_notes[:1000],
            "workspace": ws.get("workspace", {}),
        }