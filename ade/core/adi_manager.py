"""ADI project bootstrap, isolation, and artifact management."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ade.core.config import get_config
from ade.tools.docker_tool import DockerTool, DockerToolError

logger = logging.getLogger(__name__)

CODE_BLOCK_RE = re.compile(
    r"```(?P<lang>\w+)?\s*(?P<filename>[^\n]*)\n(?P<code>.*?)```",
    re.DOTALL,
)


@dataclass
class ADIProject:
    id: str
    name: str
    idea: str
    path: str
    network: str
    status: str = "bootstrapping"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    task_id: str | None = None
    isolation_enabled: bool = True
    acceptance_status: str = "pending"
    accepted_at: str | None = None
    last_revision_feedback: str = ""
    revision_count: int = 0
    pending_revision_id: int | None = None
    deploy_status: str = ""
    rebuild_status: str = ""
    rebuild_phase: str = ""
    processing_status: str = ""
    workspace_port: int | None = None
    workspace_mode: str = ""
    recovery_attempts: int = 0
    recovery_max_attempts: int = 0
    recovery_status: str = ""
    recovery_phase: str = ""
    recovery_last_decision: str = ""
    recovery_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ADIManager:
    """Creates isolated ADI workspaces under projects/."""

    def __init__(self, docker_tool: DockerTool | None = None) -> None:
        config = get_config()
        self.projects_dir = config.projects_dir
        self.docker = docker_tool or DockerTool()
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def project_path(self, project_id: str) -> Path:
        return self.projects_dir / project_id

    def bootstrap(
        self,
        project_id: str,
        name: str,
        idea: str,
        *,
        task_id: str | None = None,
        enable_isolation: bool = True,
    ) -> ADIProject:
        path = self.project_path(project_id)
        path.mkdir(parents=True, exist_ok=True)
        for subdir in ("src", "spec", "review", "data"):
            (path / subdir).mkdir(exist_ok=True)

        network = ""
        isolation = enable_isolation and self.docker.is_available()
        if isolation:
            try:
                network = self.docker.create_network(project_id)
            except DockerToolError as exc:
                logger.warning("ADI isolation disabled for %s: %s", project_id, exc)
                isolation = False

        project = ADIProject(
            id=project_id,
            name=name,
            idea=idea,
            path=str(path),
            network=network,
            status="ready",
            task_id=task_id,
            isolation_enabled=isolation,
        )

        self._write_initial_manifest(project)
        self._write_compose(project)
        self._write_readme(project)
        logger.info("Bootstrapped ADI project %s at %s", project_id, path)
        return project

    def _write_initial_manifest(self, project: ADIProject) -> None:
        manifest_path = self.project_path(project.id) / "manifest.json"
        manifest_path.write_text(
            json.dumps(project.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _write_readme(self, project: ADIProject) -> None:
        readme = self.project_path(project.id) / "README.md"
        readme.write_text(
            f"# {project.name}\n\n"
            f"**ADI ID:** `{project.id}`\n\n"
            f"## Idea\n\n{project.idea}\n\n"
            f"## Isolation\n\n"
            f"- Network: `{project.network or 'none'}`\n"
            f"- Enabled: `{project.isolation_enabled}`\n",
            encoding="utf-8",
        )

    def _write_compose(self, project: ADIProject) -> None:
        from ade.tools.docker_paths import resolve_docker_bind_source

        compose_path = self.project_path(project.id) / "docker-compose.yml"
        host_path = resolve_docker_bind_source(self.project_path(project.id))
        src_mount = f"{host_path / 'src'}:/workspace/src"
        data_mount = f"{host_path / 'data'}:/workspace/data"
        network_block = ""
        if project.network:
            network_block = f"""
networks:
  adi_net:
    external: true
    name: {project.network}
"""
        compose_path.write_text(
            f"# ADI workspace — {project.name}\n"
            f"services:\n"
            f"  workspace:\n"
            f"    image: python:3.12-slim\n"
            f"    container_name: ade-adi-{project.id}-workspace\n"
            f"    working_dir: /workspace\n"
            f"    volumes:\n"
            f"      - {src_mount}\n"
            f"      - {data_mount}\n"
            f"    command: sleep infinity\n"
            f"    restart: unless-stopped\n"
            f"{network_block}",
            encoding="utf-8",
        )

    def write_tz(self, project_id: str, content: str, *, update_status: bool = True) -> Path:
        path = self.project_path(project_id) / "spec" / "TZ.md"
        path.write_text(content, encoding="utf-8")
        if update_status:
            self._update_status(project_id, "tz_ready")
        return path

    def write_spec(self, project_id: str, content: str, *, update_status: bool = True) -> Path:
        path = self.project_path(project_id) / "spec" / "SPEC.md"
        path.write_text(content, encoding="utf-8")
        if update_status:
            self._update_status(project_id, "spec_ready")
        return path

    def write_code(self, project_id: str, content: str, *, update_status: bool = True) -> list[Path]:
        blocks = extract_code_blocks(content)
        written: list[Path] = []
        src_dir = self.project_path(project_id) / "src"

        if blocks:
            for idx, (filename, code) in enumerate(blocks):
                name = filename.strip() or f"module_{idx + 1}.py"
                if "/" in name or "\\" in name:
                    name = Path(name).name
                target = src_dir / name
                target.write_text(code.strip() + "\n", encoding="utf-8")
                written.append(target)
        else:
            target = src_dir / "main.py"
            target.write_text(content, encoding="utf-8")
            written.append(target)

        if update_status:
            self._update_status(project_id, "code_ready")
        return written

    def write_review(self, project_id: str, content: str, *, update_status: bool = True) -> Path:
        path = self.project_path(project_id) / "review" / "REVIEW.md"
        path.write_text(content, encoding="utf-8")
        if update_status:
            self._update_status(project_id, "completed")
        return path

    def _read_manifest(self, project_id: str) -> dict[str, Any]:
        manifest_path = self.project_path(project_id) / "manifest.json"
        if not manifest_path.exists():
            return {}
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def _write_manifest(self, project_id: str, data: dict[str, Any]) -> None:
        data["updated_at"] = datetime.now(UTC).isoformat()
        manifest_path = self.project_path(project_id) / "manifest.json"
        manifest_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _update_status(self, project_id: str, status: str) -> None:
        data = self._read_manifest(project_id)
        if not data:
            return
        data["status"] = status
        self._write_manifest(project_id, data)

    def accept_project(self, project_id: str) -> ADIProject | None:
        data = self._read_manifest(project_id)
        if not data:
            return None
        data["acceptance_status"] = "accepted"
        data["accepted_at"] = datetime.now(UTC).isoformat()
        self._write_manifest(project_id, data)
        return self.get_project(project_id)

    def start_revision(self, project_id: str, feedback: str) -> ADIProject | None:
        data = self._read_manifest(project_id)
        if not data:
            return None
        data["acceptance_status"] = "revising"
        data["last_revision_feedback"] = feedback
        data["revision_count"] = int(data.get("revision_count", 0)) + 1
        data["accepted_at"] = None
        data["status"] = "revising"
        self._write_manifest(project_id, data)
        return self.get_project(project_id)

    def revisions_dir(self, project_id: str) -> Path:
        path = self.project_path(project_id) / "revisions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_revision_record(
        self,
        project_id: str,
        *,
        feedback: str,
        old_tz: str,
        new_tz: str,
        old_spec: str,
        new_spec: str,
        tz_sections: list[dict],
        spec_sections: list[dict],
        summary: dict[str, int],
    ) -> int:
        data = self._read_manifest(project_id)
        rev_id = int(data.get("revision_count", 1))
        record = {
            "id": rev_id,
            "feedback": feedback,
            "created_at": datetime.now(UTC).isoformat(),
            "old_tz": old_tz,
            "new_tz": new_tz,
            "old_spec": old_spec,
            "new_spec": new_spec,
            "tz_sections": tz_sections,
            "spec_sections": spec_sections,
            "summary": summary,
            "confirmed": False,
        }
        path = self.revisions_dir(project_id) / f"rev-{rev_id}.json"
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        data["pending_revision_id"] = rev_id
        data["acceptance_status"] = "pending_review"
        data["status"] = "revision_review"
        self._write_manifest(project_id, data)
        return rev_id

    def get_revision(self, project_id: str, revision_id: int) -> dict[str, Any] | None:
        path = self.revisions_dir(project_id) / f"rev-{revision_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def get_latest_revision(self, project_id: str) -> dict[str, Any] | None:
        data = self._read_manifest(project_id)
        rev_id = data.get("pending_revision_id") or data.get("revision_count")
        if not rev_id:
            return None
        return self.get_revision(project_id, int(rev_id))

    def confirm_revision(self, project_id: str, revision_id: int) -> ADIProject | None:
        record = self.get_revision(project_id, revision_id)
        if not record:
            return None
        if record.get("confirmed"):
            return self.get_project(project_id)
        record["confirmed"] = True
        record["confirmed_at"] = datetime.now(UTC).isoformat()
        path = self.revisions_dir(project_id) / f"rev-{revision_id}.json"
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        data = self._read_manifest(project_id)
        data["pending_revision_id"] = None
        data["acceptance_status"] = "pending"
        data["status"] = "rebuilding"
        data["rebuild_status"] = "queued"
        self._write_manifest(project_id, data)
        return self.get_project(project_id)

    def set_rebuild_status(
        self,
        project_id: str,
        status: str,
        *,
        revision_id: int | None = None,
        phase: str = "",
    ) -> None:
        data = self._read_manifest(project_id)
        if not data:
            return
        data["rebuild_status"] = status
        if phase:
            data["rebuild_phase"] = phase
        data["status"] = "rebuilding" if status in ("queued", "rebuilding") else data.get("status", status)
        if revision_id is not None:
            data["last_confirmed_revision_id"] = revision_id
        self._write_manifest(project_id, data)

    def set_processing_status(self, project_id: str, status: str) -> None:
        data = self._read_manifest(project_id)
        if not data:
            return
        data["processing_status"] = status
        if status:
            data["status"] = "processing"
        self._write_manifest(project_id, data)

    def clear_processing_status(self, project_id: str) -> None:
        data = self._read_manifest(project_id)
        if not data:
            return
        data["processing_status"] = ""
        if data.get("status") == "processing":
            data["status"] = "revision_review"
        self._write_manifest(project_id, data)

    def complete_rebuild(self, project_id: str, *, deploy_status: str = "") -> ADIProject | None:
        data = self._read_manifest(project_id)
        if not data:
            return None
        data["status"] = "completed"
        data["rebuild_status"] = "completed"
        data["rebuild_phase"] = "done"
        data["processing_status"] = ""
        data["deploy_status"] = deploy_status or "unknown"
        data["acceptance_status"] = "pending"
        self._write_manifest(project_id, data)
        return self.get_project(project_id)

    def fail_rebuild(self, project_id: str, error: str) -> ADIProject | None:
        data = self._read_manifest(project_id)
        if not data:
            return None
        data["status"] = "completed"
        data["rebuild_status"] = "failed"
        data["rebuild_error"] = error
        self._write_manifest(project_id, data)
        return self.get_project(project_id)

    def recovery_limit(self, project_id: str) -> int:
        data = self._read_manifest(project_id)
        override = int(data.get("recovery_max_attempts", 0) or 0)
        if override > 0:
            return override
        return get_config().max_recovery_attempts

    def reset_recovery(self, project_id: str) -> None:
        data = self._read_manifest(project_id)
        if not data:
            return
        data["recovery_attempts"] = 0
        data["recovery_status"] = ""
        data["recovery_phase"] = ""
        data["recovery_last_decision"] = ""
        data["recovery_message"] = ""
        data.pop("rebuild_error", None)
        self._write_manifest(project_id, data)

    def begin_recovery_attempt(
        self,
        project_id: str,
        *,
        phase: str,
        decision: str,
        message: str,
    ) -> tuple[int, int]:
        """Increment attempt counter and mark project as recovering. Returns (attempt, limit)."""
        data = self._read_manifest(project_id)
        if not data:
            return 0, 0
        attempt = int(data.get("recovery_attempts", 0)) + 1
        limit = self.recovery_limit(project_id)
        data["recovery_attempts"] = attempt
        data["recovery_status"] = "recovering"
        data["recovery_phase"] = phase
        data["recovery_last_decision"] = decision
        data["recovery_message"] = message
        data["rebuild_status"] = "recovering"
        data["rebuild_phase"] = phase
        data["status"] = "rebuilding"
        self._write_manifest(project_id, data)
        return attempt, limit

    def escalate_recovery(self, project_id: str, *, error: str, message: str) -> ADIProject | None:
        data = self._read_manifest(project_id)
        if not data:
            return None
        attempt = int(data.get("recovery_attempts", 0))
        limit = self.recovery_limit(project_id)
        data["recovery_status"] = "escalated"
        data["recovery_phase"] = "escalated"
        data["recovery_last_decision"] = "escalate"
        data["recovery_message"] = message
        data["status"] = "completed"
        data["rebuild_status"] = "failed"
        data["rebuild_phase"] = "failed"
        data["rebuild_error"] = error[:500]
        data["deploy_status"] = data.get("deploy_status") or "failed"
        self._write_manifest(project_id, data)
        logger.warning(
            "Recovery escalated for %s after %s/%s attempts: %s",
            project_id,
            attempt,
            limit,
            error[:200],
        )
        return self.get_project(project_id)

    def deploy_project(self, project_id: str, *, use_agent: bool = False) -> dict[str, Any]:
        from ade.core.deployer import DeployerService

        result = DeployerService(adi_manager=self).deploy(project_id, use_agent=use_agent)
        if result.get("status") == "ok":
            return {"status": "running", "message": "deployed", "workspace": result.get("workspace")}
        if result.get("message") == "not_found":
            return {"status": "skipped", "message": "not_found"}
        return {
            "status": "failed",
            "message": result.get("detail") or result.get("message", "deploy_failed"),
        }

    def ensure_pending_revision_record(self, project_id: str) -> int | None:
        """Backfill revision review for projects revised before diff tracking existed."""
        data = self._read_manifest(project_id)
        if not data:
            return None
        rev_count = int(data.get("revision_count", 0))
        if rev_count < 1:
            return None
        if data.get("pending_revision_id"):
            return int(data["pending_revision_id"])

        rev_path = self.revisions_dir(project_id) / f"rev-{rev_count}.json"
        if rev_path.exists():
            record = json.loads(rev_path.read_text(encoding="utf-8"))
            if not record.get("confirmed"):
                data["pending_revision_id"] = rev_count
                data["acceptance_status"] = "pending_review"
                data["status"] = "revision_review"
                self._write_manifest(project_id, data)
            return rev_count

        from ade.core.revision_diff import compare_sections, summarize_changes

        root = self.project_path(project_id)
        tz_path = root / "spec" / "TZ.md"
        spec_path = root / "spec" / "SPEC.md"
        new_tz = tz_path.read_text(encoding="utf-8") if tz_path.exists() else ""
        new_spec = spec_path.read_text(encoding="utf-8") if spec_path.exists() else ""
        feedback = data.get("last_revision_feedback", "Доработка без сохранённого diff")

        tz_sections = compare_sections("", new_tz)
        spec_sections = compare_sections("", new_spec)
        summary = summarize_changes(tz_sections, spec_sections)

        record = {
            "id": rev_count,
            "feedback": feedback,
            "created_at": data.get("updated_at", datetime.now(UTC).isoformat()),
            "old_tz": "",
            "new_tz": new_tz,
            "old_spec": "",
            "new_spec": new_spec,
            "tz_sections": tz_sections,
            "spec_sections": spec_sections,
            "summary": summary,
            "confirmed": False,
            "backfilled": True,
        }
        rev_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        data["pending_revision_id"] = rev_count
        data["acceptance_status"] = "pending_review"
        data["status"] = "revision_review"
        self._write_manifest(project_id, data)
        logger.info("Backfilled revision record rev-%s for %s", rev_count, project_id)
        return rev_count

    def complete_revision(self, project_id: str) -> ADIProject | None:
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> ADIProject | None:
        manifest_path = self.project_path(project_id) / "manifest.json"
        if not manifest_path.exists():
            return None
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return ADIProject(**{k: v for k, v in data.items() if k in ADIProject.__dataclass_fields__})

    def get_project_detail(self, project_id: str) -> dict[str, Any] | None:
        project = self.get_project(project_id)
        if not project:
            return None

        root = self.project_path(project_id)
        tz_path = root / "spec" / "TZ.md"
        spec_path = root / "spec" / "SPEC.md"
        review_path = root / "review" / "REVIEW.md"
        src_dir = root / "src"

        src_files: list[dict[str, str]] = []
        if src_dir.is_dir():
            for file_path in sorted(src_dir.iterdir()):
                if file_path.is_file():
                    src_files.append(
                        {
                            "name": file_path.name,
                            "content": file_path.read_text(encoding="utf-8"),
                        }
                    )

        from ade.core.deliverable import read_deliverable

        return {
            "project": project,
            "tz": tz_path.read_text(encoding="utf-8") if tz_path.exists() else "",
            "spec": spec_path.read_text(encoding="utf-8") if spec_path.exists() else "",
            "review": review_path.read_text(encoding="utf-8") if review_path.exists() else "",
            "src_files": src_files,
            "deliverable": read_deliverable(root),
        }

    def list_projects(self) -> list[ADIProject]:
        projects: list[ADIProject] = []
        if not self.projects_dir.exists():
            return projects
        for entry in sorted(self.projects_dir.iterdir()):
            if entry.is_dir() and (entry / "manifest.json").exists():
                project = self.get_project(entry.name)
                if project:
                    projects.append(project)
        return sorted(projects, key=lambda p: p.created_at, reverse=True)

    def get_delete_block_reason(
        self,
        project_id: str,
        *,
        task_status: str = "",
    ) -> str | None:
        project = self.get_project(project_id)
        if not project:
            return "not_found"
        if project.status == "rebuilding":
            return "rebuild_in_progress"
        if getattr(project, "processing_status", ""):
            return "processing_in_progress"
        if project.pending_revision_id:
            return "pending_revision_review"
        if task_status in ("running", "awaiting_approval", "queued"):
            return "workflow_in_progress"
        return None

    def _compose_down(self, project_id: str) -> None:
        path = self.project_path(project_id)
        compose = path / "docker-compose.yml"
        if not compose.exists() or not self.docker.is_available():
            return
        from ade.tools.compose_runner import run_compose

        result = run_compose(path, "down", "--remove-orphans")
        if result.returncode == 0:
            logger.info("compose down ok for %s", project_id)

    def teardown(self, project_id: str) -> None:
        project = self.get_project(project_id)
        if not project:
            return
        self._compose_down(project_id)
        if project.isolation_enabled and project.network:
            container_name = f"ade-adi-{project_id}-workspace"
            self.docker.stop_container(container_name)
            self.docker.remove_container(container_name, force=True)
            self.docker.remove_network(project_id)

    DUPLICATE_SKIP_NAMES = frozenset(
        {"node_modules", ".expo", "expo-mobile.zip", "revisions"}
    )

    def suggest_duplicate_name(self, source_name: str) -> str:
        """Pick the next version label: «Name V2», «Name V3», …"""
        names = {project.name for project in self.list_projects()}
        match = re.match(r"^(.*)\s+V(\d+)$", source_name.strip())
        base = match.group(1).strip() if match else source_name.strip()
        start = int(match.group(2)) + 1 if match else 2
        version = start
        while f"{base} V{version}" in names:
            version += 1
        return f"{base} V{version}"

    def duplicate_project(self, source_id: str) -> dict[str, Any]:
        """Copy project artifacts into a new ADI for the next development version."""
        source = self.get_project(source_id)
        if not source:
            return {"status": "error", "message": "not_found"}

        src_path = self.project_path(source_id)
        if not src_path.is_dir() or not (src_path / "manifest.json").exists():
            return {"status": "error", "message": "not_found"}

        new_id = str(uuid.uuid4())
        new_name = self.suggest_duplicate_name(source.name)
        dst_path = self.project_path(new_id)

        def _ignore(_directory: str, names: list[str]) -> set[str]:
            return {name for name in names if name in self.DUPLICATE_SKIP_NAMES}

        try:
            shutil.copytree(src_path, dst_path, ignore=_ignore, dirs_exist_ok=False)
        except OSError as exc:
            logger.exception("Duplicate copy failed for %s", source_id)
            if dst_path.exists():
                shutil.rmtree(dst_path, ignore_errors=True)
            return {"status": "error", "message": "copy_failed", "detail": str(exc)[:300]}

        old_manifest = self._read_manifest(new_id)
        network = ""
        isolation = source.isolation_enabled and self.docker.is_available()
        if isolation:
            try:
                network = self.docker.create_network(new_id)
            except DockerToolError as exc:
                logger.warning("Isolation disabled for duplicate %s: %s", new_id, exc)
                isolation = False

        artifact_status = old_manifest.get("status", source.status)
        if artifact_status not in ("completed", "ready", "revision_review"):
            artifact_status = "completed" if (dst_path / "spec" / "SPEC.md").exists() else "ready"

        new_project = ADIProject(
            id=new_id,
            name=new_name,
            idea=old_manifest.get("idea", source.idea),
            path=str(dst_path),
            network=network,
            status=artifact_status,
            task_id=None,
            isolation_enabled=isolation,
            acceptance_status="pending",
            accepted_at=None,
            last_revision_feedback="",
            revision_count=0,
            pending_revision_id=None,
            deploy_status="",
            rebuild_status="",
            rebuild_phase="",
            processing_status="",
            workspace_port=None,
            workspace_mode="",
        )
        manifest = new_project.to_dict()
        manifest["cloned_from"] = source_id
        manifest["cloned_at"] = datetime.now(UTC).isoformat()
        self._write_manifest(new_id, manifest)
        self._write_compose(new_project)
        self._refresh_duplicate_deliverable(new_id, new_name, dst_path)

        logger.info("Duplicated project %s -> %s (%s)", source_id, new_id, new_name)
        return {
            "status": "ok",
            "project_id": new_id,
            "name": new_name,
            "cloned_from": source_id,
            "redirect_url": f"/projects/{new_id}",
        }

    def _refresh_duplicate_deliverable(
        self, project_id: str, project_name: str, project_path: Path
    ) -> None:
        from ade.core.deliverable import build_deliverable, write_deliverable_manifest

        root = project_path
        spec_path = root / "spec" / "SPEC.md"
        spec = spec_path.read_text(encoding="utf-8") if spec_path.exists() else ""
        src_dir = root / "src"
        code = ""
        if src_dir.is_dir():
            code = "\n".join(
                f.read_text(encoding="utf-8")
                for f in sorted(src_dir.iterdir())
                if f.is_file()
            )
        idea = self._read_manifest(project_id).get("idea", "")
        deliverable = build_deliverable(
            project_id, project_name, idea, spec, code, project_path
        )
        write_deliverable_manifest(project_path, deliverable)

    def delete_project(self, project_id: str, *, task_status: str = "") -> dict[str, Any]:
        block = self.get_delete_block_reason(project_id, task_status=task_status)
        if block:
            return {"status": "error", "message": block}

        path = self.project_path(project_id)
        if not path.is_dir() or not (path / "manifest.json").exists():
            return {"status": "error", "message": "not_found"}

        self.teardown(project_id)
        shutil.rmtree(path)
        logger.info("Deleted ADI project %s", project_id)
        return {"status": "ok", "project_id": project_id}


def extract_code_blocks(content: str) -> list[tuple[str, str]]:
    """Extract fenced code blocks; optional first-line filename hint."""
    blocks: list[tuple[str, str]] = []
    for match in CODE_BLOCK_RE.finditer(content):
        filename = match.group("filename") or ""
        code = match.group("code") or ""
        if code.strip():
            blocks.append((filename, code))
    return blocks