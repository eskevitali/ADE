"""Deployer agent and workspace deployment orchestration."""

from __future__ import annotations

import logging
import hashlib
import json
import time
import subprocess
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ade.core.agent_team import AgentRole, AgentTeam
from ade.core.team_config import get_workflow_prompt
from ade.core.adi_manager import ADIManager
from ade.core.config import get_config
from ade.core.engineering import ReleaseService, atomic_json, project_lock
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
        return WORKSPACE_PORT_BASE + (int(hashlib.sha256(project_id.encode()).hexdigest()[:8], 16) % 900)

    _PYTHON_SERVER_MARKERS = (
        "uvicorn",
        "fastapi",
        "flask",
        "app.run(",
        "httpserver",
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

    def _ensure_compose(self, project_id: str, project_name: str, *, snapshot: Path | None = None, image: str | None = None) -> Path:
        path = self.adi.project_path(project_id)
        compose_path = path / "docker-compose.yml"
        project = self.adi.get_project(project_id)
        network = project.network if project else ""
        port = self._workspace_port(project_id)
        cmd, container_port, mode = self._detect_start_command(snapshot or path)

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
        src_host = resolve_docker_bind_source((snapshot or path) / "src")
        src_mount = f"{src_host}:/workspace/src:ro"
        data_mount = f"{host_path / 'data'}:/workspace/data"
        extra_volumes = ""
        if mode in ("mobile_preview", "simulator_preview"):
            workdir = "/workspace/preview"
            service_cmd = "python -m http.server 8080"
            preview_mount = f"{host_path / 'preview'}:/workspace/preview"
            extra_volumes = f"      - {preview_mount}\n"
            ports_block = f"""
    ports:
      - "127.0.0.1:{port}:8080"
"""
        elif mode == "web_static":
            workdir = "/workspace/src"
            service_cmd = "python -m http.server 8080"
            ports_block = f"""
    ports:
      - "127.0.0.1:{port}:8080"
"""
        elif mode == "python_app":
            service_cmd = "python src/main.py"
            ports_block = f"""
    ports:
      - "127.0.0.1:{port}:8000"
"""
        elif mode == "python_script":
            service_cmd = "python src/main.py"

        if snapshot is not None:
            # Release applications are reachable only through ADE's authenticated proxy.
            ports_block = ""
        safe_name = project_name.replace("\n", " ").replace("\r", " ")
        compose_body = (
            f"# ADI workspace — {safe_name}\n"
            f"# mode: {mode}\n"
            f"services:\n"
            f"  workspace:\n"
            f"    image: {image or get_config().workspace_image}\n"
            f"    container_name: ade-adi-{project_id}-workspace\n"
            f"    working_dir: {workdir}\n"
            f"    volumes:\n"
            f"      - {src_mount}\n"
            f"      - {data_mount}\n"
            f"{extra_volumes}"
            f"    command: {service_cmd}\n"
            f"    restart: '{'no' if mode == 'python_script' else 'unless-stopped'}'\n"
            f"    read_only: true\n"
            f"    user: '65534:65534'\n"
            f"    cap_drop: [ALL]\n"
            f"    security_opt: [no-new-privileges:true]\n"
            f"    pids_limit: 128\n"
            f"    mem_limit: 512m\n"
            f"    cpus: 1\n"
            f"    environment: [PYTHONDONTWRITEBYTECODE=1]\n"
            f"    tmpfs: ['/tmp:rw,noexec,nosuid,size=64m']\n"
            f"{ports_block}"
            f"{service_networks}"
        )
        if mode == "python_script":
            compose_body += "    network_mode: none\n"
        if networks_decl:
            compose_body += f"networks:{networks_decl}"
        compose_path.write_text(compose_body, encoding="utf-8")

        data = self.adi._read_manifest(project_id)
        if data:
            data["workspace_port"] = port if has_http_server and snapshot is None else None
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
        active = manifest.get("active_release_id")
        if active:
            project_path = project_path / "releases" / active
        mode = manifest.get("workspace_mode", "idle")
        workspace_url, url_label = self._user_facing_url(
            project_id,
            project_path,
            mode=mode,
            host_port=workspace_port,
            running=running,
        )

        if active and running and mode in WORKSPACE_CONTAINER_PORTS:
            workspace_url, url_label = f"/run/{project_id}/", "Открыть проверенный релиз"
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

    def _wait_ready(self, project_id: str, mode: str) -> bool:
        container = f"ade-adi-{project_id}-workspace"
        port = WORKSPACE_CONTAINER_PORTS.get(mode)
        for _ in range(15):
            if port:
                probe = (
                    "import urllib.request; "
                    f"r=urllib.request.urlopen('http://127.0.0.1:{port}/', timeout=2); "
                    "assert r.status < 500"
                )
                command = ["docker", "exec", container, "python", "-c", probe]
            else:
                command = ["docker", "inspect", container, "--format",
                           "{{.State.Status}}|{{.State.ExitCode}}"]
            try:
                result = subprocess.run(command, capture_output=True, text=True,
                                        timeout=5, check=False)
                if port and result.returncode == 0:
                    return True
                if not port and result.stdout.strip() == "exited|0":
                    return True
                if not port and result.stdout.strip().startswith("exited|"):
                    return False
            except (OSError, subprocess.TimeoutExpired):
                return False
            time.sleep(1)
        return False

    def _activate(self, project_id: str, release_id: str) -> dict[str, Any]:
        releases = ReleaseService(self.adi)
        snapshot = releases.verify(project_id, release_id)
        report = json.loads((snapshot / "verification.json").read_text())
        if not report.get("passed") or report.get("release_id") != release_id:
            raise ValueError("Release has no passing verification")
        identity = json.loads((snapshot / "release.json").read_text())
        project = self.adi.get_project(project_id)
        self._ensure_compose(project_id, project.name, snapshot=snapshot,
                             image=identity["workspace_image"])
        result = self._compose_up(self.adi.project_path(project_id))
        mode = self.adi._read_manifest(project_id).get("workspace_mode", "idle")
        if result.returncode != 0 or not self._wait_ready(project_id, mode):
            return {"status": "error", "message": "readiness_failed",
                    "detail": (result.stderr or result.stdout or "Readiness probe failed")[-2000:]}
        return {"status": "ok", "mode": mode}

    def deploy(self, project_id: str, *, use_agent: bool = True) -> dict[str, Any]:
        project = self.adi.get_project(project_id)
        if not project:
            return {"status": "error", "message": "not_found"}
        if project.status == "rebuilding":
            return {"status": "error", "message": "rebuild_in_progress"}
        root = self.adi.project_path(project_id)
        with project_lock(root):
            report = ReleaseService(self.adi)._prepare_locked(project_id, root)
            if not report["passed"]:
                failures = [c['name'] + ': ' + str(c.get('detail', 'failed'))
                            for c in report['checks'] if not c['passed']]
                return {"status": "error", "message": "quality_gate_failed",
                        "detail": "\n".join(failures), "verification": report}
            release_id = report['release_id']
            previous = self.adi._read_manifest(project_id).get('active_release_id')
            try:
                result = self._activate(project_id, release_id)
            except Exception as exc:
                result = {"status": "error", "message": "deploy_failed", "detail": str(exc)[:2000]}
            if result['status'] != 'ok':
                rollback = None
                if previous:
                    try:
                        rollback = self._activate(project_id, previous)
                    except Exception as exc:
                        rollback = {"status": "error", "detail": str(exc)[:500]}
                data = self.adi._read_manifest(project_id)
                data.update(deploy_status='failed', deploy_error=result.get('detail', ''),
                            rollback_status=rollback.get('status') if rollback else 'unavailable')
                self.adi._write_manifest(project_id, data)
                atomic_json(root / 'releases' / release_id / 'deployment.json',
                            {**result, 'release_id': release_id, 'rollback': rollback})
                return {**result, 'release_id': release_id, 'rollback': rollback}
            data = self.adi._read_manifest(project_id)
            data.update(active_release_id=release_id, previous_release_id=previous,
                        deploy_status='running' if result['mode'] != 'python_script' else 'completed')
            data.pop('deploy_error', None)
            self.adi._write_manifest(project_id, data)
            atomic_json(root / 'releases' / release_id / 'deployment.json',
                        {'status': 'ok', 'release_id': release_id, 'previous_release_id': previous})
            return {'status': 'ok', 'message': 'deployed', 'release_id': release_id,
                    'verification': report, 'workspace': self.get_workspace_status(project_id)['workspace']}

    def rollback(self, project_id: str) -> dict[str, Any]:
        root = self.adi.project_path(project_id)
        with project_lock(root):
            data = self.adi._read_manifest(project_id)
            previous = data.get('previous_release_id')
            if not previous:
                return {'status': 'error', 'message': 'no_previous_release'}
            result = self._activate(project_id, previous)
            if result['status'] == 'ok':
                data = self.adi._read_manifest(project_id)
                current = data.get('active_release_id')
                data.update(active_release_id=previous, previous_release_id=current,
                            deploy_status='running' if result['mode'] != 'python_script' else 'completed')
                self.adi._write_manifest(project_id, data)
            return {**result, 'release_id': previous}
