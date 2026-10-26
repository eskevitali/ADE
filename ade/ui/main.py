"""FastAPI application with Browser UI and WebSocket workflow streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from ade import __version__
from ade.core.adi_manager import ADIManager
from ade.core.agent_team import DEFAULT_MODELS, AgentConfig, AgentRole
from ade.core.team_config import SUGGESTED_MODELS, get_team_manager, load_agent_team
from ade.core.approval_gate import approval_gate
from ade.core.auth import (
    auth_middleware,
    get_current_user,
    login_user,
    logout_user,
    require_user,
    verify_credentials,
    websocket_authenticated,
)
from ade.core.config import get_config
from ade.core.deliverable import (
    build_deliverable,
    ensure_expo_project,
    ensure_mobile_mockup,
    ensure_timer_simulator,
    needs_interactive_simulator,
    read_deliverable,
    write_deliverable_manifest,
)
from ade.core.deployer import DeployerService
from ade.core.engineering import ReleaseService
from ade.memory.lessons import LessonStore
from ade.core.revision_diff import compare_sections, summarize_changes
from ade.core.spec_parser import parse_sections
from ade.core.model_registry import format_model_display, get_model_style
from ade.memory.event_store import EventStore
from ade.memory.vector_store import VectorStore
from ade.workflows.bootstrap_cycle import BootstrapCycleOrchestrator
from ade.workflows.hitl_helpers import (
    discuss_idea,
    revise_document_section,
    revise_tz_and_spec_from_feedback,
)
from ade.workflows.dev_cycle import DevCycleOrchestrator
from ade.workflows.orchestrator import DevOrchestrator
from ade.workflows.revision_rebuild import RevisionRebuildOrchestrator

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


@dataclass
class TaskRecord:
    id: str
    task: str
    status: str = "queued"
    phase: str = "idea"
    workflow: str = "dev_cycle"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    project_id: str = ""
    project_name: str = ""
    human_in_loop: bool = True
    pending_gate: str = ""
    tz: str = ""
    spec: str = ""
    code: str = ""
    review: str = ""
    discussion: list[dict[str, str]] = field(default_factory=list)
    deliverable: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def summary(self) -> str:
        return self.task[:80] + ("…" if len(self.task) > 80 else "")


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []
        self.subscriptions: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)
        for subs in self.subscriptions.values():
            if websocket in subs:
                subs.remove(websocket)

    def subscribe(self, task_id: str, websocket: WebSocket) -> None:
        self.subscriptions.setdefault(task_id, []).append(websocket)

    async def broadcast(self, message: dict[str, Any], task_id: str | None = None) -> None:
        payload = json.dumps(message, ensure_ascii=False)
        targets = list(self.active)
        if task_id and task_id in self.subscriptions:
            targets = self.subscriptions[task_id]
        dead: list[WebSocket] = []
        for connection in targets:
            try:
                await connection.send_text(payload)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)


manager = ConnectionManager()
team_manager = get_team_manager()
team = load_agent_team()
tasks: dict[str, TaskRecord] = {}
vector_store = VectorStore()
event_store = EventStore()
adi_manager = ADIManager()
deployer_service = DeployerService(adi_manager=adi_manager, team=team)


def reload_runtime_team() -> None:
    """Reload agent team from governance/agents after config edits."""
    global team, deployer_service
    team = load_agent_team()
    deployer_service = DeployerService(adi_manager=adi_manager, team=team)


def _log_event(
    project_id: str,
    event_type: str,
    data: dict[str, Any] | None = None,
    *,
    actor: str = "system",
) -> None:
    if not project_id:
        return
    event_store.record(project_id, event_type, data=data, actor=actor)


class TaskRequest(BaseModel):
    task: str = Field(..., min_length=1)
    max_iterations: int = Field(default=3, ge=1, le=20)
    workflow: str = Field(default="dev_cycle")
    project_name: str = Field(default="")
    human_in_loop: bool = Field(default=True)


class ApprovalRequest(BaseModel):
    gate: str = Field(..., min_length=1)
    comment: str = Field(default="")


class DiscussRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ReviseSectionRequest(BaseModel):
    gate: str = Field(..., pattern="^(tz|spec)$")
    section_id: str = Field(..., min_length=1)
    comment: str = Field(..., min_length=1)


class ReflectionFeedbackRequest(BaseModel):
    feedback: str = Field(..., min_length=3)


class DeleteProjectRequest(BaseModel):
    confirm_name: str = Field(..., min_length=1)


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


def _serialize_messages(state: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for msg in state.get("messages", []):
        role = getattr(msg, "type", "unknown")
        name = getattr(msg, "name", None) or role
        content = getattr(msg, "content", "")
        if not isinstance(content, str):
            content = str(content)
        items.append({"role": role, "agent": name, "content": content[:500]})
    return items


def _make_event_callback(task_id: str, loop: asyncio.AbstractEventLoop):
    def on_event(event: str, data: dict[str, Any]) -> None:
        record = tasks.get(task_id)
        if record and "phase" in data:
            record.phase = data["phase"]
        if record and event == "awaiting_approval":
            record.status = "awaiting_approval"
            record.pending_gate = data.get("gate", "")
        if record and event == "approval_resolved":
            record.pending_gate = ""
            if record.status == "awaiting_approval":
                record.status = "running"
        if record and event == "document_ready":
            gate = data.get("gate", "")
            doc = data.get("document", "")
            if gate == "tz":
                record.tz = doc
            elif gate == "spec":
                record.spec = doc
        if record and event == "deliverable_ready":
            record.deliverable = data
        if record and event == "step_completed":
            node = data.get("node", "")
            if node == "coder" and record.project_id:
                _log_event(record.project_id, "code_generated", {"phase": data.get("phase")})
        if record and event == "workflow_completed":
            final_status = data.get("status", "completed")
            record.status = final_status if final_status != "completed" else "completed"
            record.pending_gate = ""
            if record.project_id and final_status == "completed":
                _log_event(record.project_id, "workflow_completed", {"task_id": task_id})
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({"event": event, "task_id": task_id, **data}, task_id=task_id),
            loop,
        )

    return on_event


async def _run_dev_cycle(
    task_id: str,
    task: str,
    *,
    project_id: str = "",
    human_in_loop: bool = True,
) -> None:
    record = tasks[task_id]
    record.status = "running"
    loop = asyncio.get_running_loop()
    callback = _make_event_callback(task_id, loop)

    await manager.broadcast({"event": "workflow_started", "task_id": task_id, "task": task}, task_id)

    try:
        if project_id:
            orchestrator = BootstrapCycleOrchestrator(
                team=team,
                on_event=callback,
                task_id=task_id,
                project_id=project_id,
                adi_manager=adi_manager,
                human_in_loop=human_in_loop,
                discussion=record.discussion,
            )
        else:
            orchestrator = DevCycleOrchestrator(team=team, on_event=callback)

        result = await asyncio.to_thread(orchestrator.run, task)
        record.spec = result.get("spec", "")
        record.code = result.get("code", "")
        record.review = result.get("review", "")
        record.status = result.get("status", "completed")
        record.phase = result.get("phase", "review")
        record.pending_gate = ""
        if project_id and not record.deliverable:
            record.deliverable = read_deliverable(adi_manager.project_path(project_id)) or {}

        await asyncio.to_thread(
            vector_store.store_workflow_result,
            task,
            record.spec,
            record.code,
            record.review,
            {"task_id": task_id, "project_id": project_id},
        )

        await manager.broadcast(
            {
                "event": "task_completed",
                "task_id": task_id,
                "status": record.status,
                "project_id": project_id,
                "spec": record.spec[:2000],
                "code": record.code[:2000],
                "review": record.review[:2000],
                "deliverable": record.deliverable,
                "messages": _serialize_messages(result),
            },
            task_id,
        )
    except Exception as exc:
        logger.exception("Task %s failed", task_id)
        record.status = "failed"
        record.error = str(exc)
        record.pending_gate = ""
        await manager.broadcast(
            {"event": "task_failed", "task_id": task_id, "error": str(exc)},
            task_id,
        )
    finally:
        approval_gate.clear_task(task_id)


async def _run_supervisor(task_id: str, task: str, max_iterations: int) -> None:
    record = tasks[task_id]
    record.status = "running"
    await manager.broadcast({"event": "task_started", "task_id": task_id, "task": task}, task_id)
    try:
        orchestrator = DevOrchestrator(team=team, max_iterations=max_iterations)
        result = await asyncio.to_thread(orchestrator.run, task)
        record.status = result.get("status", "completed")
        await manager.broadcast(
            {
                "event": "task_completed",
                "task_id": task_id,
                "status": record.status,
                "iteration": result.get("iteration", 0),
                "messages": _serialize_messages(result),
            },
            task_id,
        )
    except Exception as exc:
        record.status = "failed"
        await manager.broadcast(
            {"event": "task_failed", "task_id": task_id, "error": str(exc)},
            task_id,
        )


async def _run_revision_rebuild(project_id: str, revision_id: int) -> None:
    adi_manager.set_rebuild_status(project_id, "rebuilding", revision_id=revision_id)
    await manager.broadcast(
        {
            "event": "rebuild_started",
            "project_id": project_id,
            "revision_id": revision_id,
        },
    )
    try:
        orchestrator = RevisionRebuildOrchestrator(team=team, adi_manager=adi_manager)
        result = await asyncio.to_thread(orchestrator.run, project_id, revision_id)
        if result.get("status") == "escalated":
            await manager.broadcast(
                {
                    "event": "recovery_escalated",
                    "project_id": project_id,
                    "revision_id": revision_id,
                    "error": result.get("error", ""),
                    "deliverable": result.get("deliverable", {}),
                },
            )
        else:
            await manager.broadcast(
                {
                    "event": "rebuild_completed",
                    "project_id": project_id,
                    "revision_id": revision_id,
                    "status": result.get("status", "completed"),
                    "deploy": result.get("deploy", {}),
                    "deliverable": result.get("deliverable", {}),
                },
            )
    except Exception as exc:
        logger.exception("Revision rebuild failed for %s", project_id)
        project = adi_manager.get_project(project_id)
        if project and getattr(project, "recovery_status", "") == "escalated":
            await manager.broadcast(
                {
                    "event": "recovery_escalated",
                    "project_id": project_id,
                    "revision_id": revision_id,
                    "error": str(exc),
                },
            )
        else:
            adi_manager.fail_rebuild(project_id, str(exc))
            await manager.broadcast(
                {
                    "event": "rebuild_failed",
                    "project_id": project_id,
                    "revision_id": revision_id,
                    "error": str(exc),
                },
            )


async def _dispatch_task(
    task_id: str,
    task: str,
    workflow: str,
    max_iterations: int = 3,
    *,
    project_id: str = "",
    human_in_loop: bool = True,
) -> None:
    if workflow == "supervisor":
        await _run_supervisor(task_id, task, max_iterations)
    else:
        await _run_dev_cycle(
            task_id,
            task,
            project_id=project_id,
            human_in_loop=human_in_loop,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    config.ensure_dirs()
    logging.basicConfig(level=config.log_level.upper())
    if event_store.is_available():
        event_store.ensure_schema()
        logger.info("PostgreSQL event store connected")
    else:
        logger.warning("PostgreSQL event store offline — events will not persist")
    logger.info("ADE v%s starting — domain: %s", __version__, config.domain)
    yield
    logger.info("ADE shutting down")


app = FastAPI(
    title="ADE v4",
    description="Autonomous Development Environment harness",
    version=__version__,
    lifespan=lifespan,
)

config = get_config()


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        return await auth_middleware(request, call_next)


app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=config.session_secret, max_age=86400 * 7,
                   https_only=config.app_env == "production", same_site="lax")
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"https://{config.domain}",
        f"http://{config.domain}",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/dashboard") -> Response:
    if get_current_user(request):
        return RedirectResponse(url=next or "/dashboard", status_code=303)
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/dashboard"
    return templates.TemplateResponse(
        request,
        "login.html",
        {"next_url": safe_next, "error": "", "username": ""},
    )


@app.post("/auth/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/dashboard"),
) -> Response:
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/dashboard"
    if not verify_credentials(username, password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "next_url": safe_next,
                "error": "Неверный логин или пароль",
                "username": username,
            },
            status_code=401,
        )
    login_user(request, username.strip())
    return RedirectResponse(url=safe_next, status_code=303)


@app.post("/auth/logout")
async def logout_submit(request: Request) -> RedirectResponse:
    logout_user(request)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.head("/health", include_in_schema=False)
async def health_head() -> Response:
    return Response(status_code=200)


def _agent_status(cfg: AgentConfig) -> str:
    config = get_config()
    if "grok" in cfg.model.lower() or "x-ai" in cfg.model.lower():
        return "online" if (config.has_xai() or config.has_openrouter()) else "offline"
    return "online" if config.has_openrouter() else "offline"


def build_team_payload(*, include_prompts: bool = False) -> dict[str, Any]:
    agents = []
    for cfg in team.agents.values():
        style = get_model_style(cfg.model)
        status = _agent_status(cfg)
        entry: dict[str, Any] = {
            "role": cfg.role.value,
            "name": cfg.name,
            "description": cfg.description,
            "model": cfg.model,
            "model_display": format_model_display(cfg.model),
            "provider": style["provider"],
            "color": style["color"],
            "badge_class": style["badge"],
            "dot_class": style["dot"],
            "status": status,
            "customized": team_manager.is_role_customized(cfg.role),
        }
        if include_prompts:
            entry["prompt"] = team_manager.read_role_prompt(cfg.role)
            entry["default_prompt"] = team_manager.read_role_default_prompt(cfg.role)
            entry["default_model"] = DEFAULT_MODELS[cfg.role]
            entry["prompt_path"] = str(team_manager.prompts_dir / f"{cfg.role.value}.md")
        agents.append(entry)
    online_count = sum(1 for a in agents if a["status"] == "online")
    return {
        "team_count": len(agents),
        "online_count": online_count,
        "agents": agents,
        "suggested_models": SUGGESTED_MODELS,
        "prompts_dir": str(team_manager.prompts_dir),
        "workflow_prompts": team_manager.list_workflow_prompts() if include_prompts else [],
    }


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: str = Depends(require_user)) -> HTMLResponse:
    sorted_tasks = sorted(tasks.values(), key=lambda t: t.created_at, reverse=True)
    team_info = build_team_payload()
    projects = adi_manager.list_projects()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "tasks": sorted_tasks,
            "projects": projects,
            "task_count": len(tasks),
            "project_count": len(projects),
            "team_count": team_info["team_count"],
            "health": "online",
            "user": user,
        },
    )


@app.get("/projects/new", response_class=HTMLResponse)
async def new_project_form(request: Request, user: str = Depends(require_user)) -> HTMLResponse:
    return templates.TemplateResponse(request, "new_project.html", {"user": user})


@app.post("/projects/new")
async def new_project_submit(
    task: str = Form(...),
    workflow: str = Form(default="dev_cycle"),
    project_name: str = Form(default=""),
    human_in_loop: str = Form(default="on"),
    _user: str = Depends(require_user),
) -> RedirectResponse:
    task_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    name = project_name.strip() or task[:60].strip()
    hitl = human_in_loop == "on"

    adi_manager.bootstrap(project_id, name, task, task_id=task_id)
    _log_event(project_id, "project_created", {"name": name, "task_id": task_id}, actor=_user)

    tasks[task_id] = TaskRecord(
        id=task_id,
        task=task,
        workflow=workflow,
        project_id=project_id,
        project_name=name,
        human_in_loop=hitl,
    )
    asyncio.create_task(
        _dispatch_task(
            task_id,
            task,
            workflow,
            project_id=project_id,
            human_in_loop=hitl,
        )
    )
    return RedirectResponse(url=f"/workflow/{task_id}", status_code=303)


@app.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_view(
    request: Request, project_id: str, user: str = Depends(require_user)
) -> HTMLResponse:
    adi_manager.ensure_pending_revision_record(project_id)
    detail = adi_manager.get_project_detail(project_id)
    if not detail:
        return HTMLResponse("<h1>Project not found</h1>", status_code=404)
    project = detail["project"]
    deliverable = detail.get("deliverable")
    if not deliverable:
        deliverable = build_deliverable(
            project.id,
            project.name,
            project.idea,
            detail["spec"],
            "\n".join(f["content"] for f in detail["src_files"]),
            adi_manager.project_path(project.id),
        )
        if needs_interactive_simulator(project.idea, detail["spec"]):
            project_path = adi_manager.project_path(project.id)
            ensure_timer_simulator(
                project_path,
                project.name,
                detail["spec"],
                feedback=project.last_revision_feedback,
            )
            deliverable = build_deliverable(
                project.id,
                project.name,
                project.idea,
                detail["spec"],
                "\n".join(f["content"] for f in detail["src_files"]),
                project_path,
            )
        elif deliverable["type"] == "mobile":
            project_path = adi_manager.project_path(project.id)
            ensure_mobile_mockup(project_path, project.name, detail["spec"])
            ensure_expo_project(project_path, project.name, detail["spec"])
            deliverable = build_deliverable(
                project.id,
                project.name,
                project.idea,
                detail["spec"],
                "\n".join(f["content"] for f in detail["src_files"]),
                project_path,
            )
        write_deliverable_manifest(adi_manager.project_path(project.id), deliverable)
    workflow_url = ""
    if project.task_id and project.task_id in tasks:
        workflow_url = f"/workflow/{project.task_id}"
    workspace_status = deployer_service.get_workspace_status(project.id)
    recent_events = event_store.list_events(project.id, limit=10)
    manifest_extra = adi_manager._read_manifest(project.id)
    return templates.TemplateResponse(
        request,
        "project.html",
        {
            "user": user,
            "project": project,
            "tz": detail.get("tz", ""),
            "spec": detail["spec"],
            "review": detail["review"],
            "src_files": detail["src_files"],
            "deliverable": deliverable,
            "workflow_url": workflow_url,
            "acceptance_status": project.acceptance_status,
            "accepted_at": project.accepted_at,
            "revision_count": project.revision_count,
            "pending_revision_id": project.pending_revision_id,
        "rebuild_status": getattr(project, "rebuild_status", "") or "",
        "rebuild_phase": getattr(project, "rebuild_phase", "") or "",
        "deploy_status": getattr(project, "deploy_status", "") or "",
        "deploy_error": manifest_extra.get("deploy_error", "") or "",
        "workspace_mode": manifest_extra.get("workspace_mode", "") or "",
        "processing_status": getattr(project, "processing_status", "") or "",
        "recovery_status": getattr(project, "recovery_status", "") or "",
        "recovery_attempts": getattr(project, "recovery_attempts", 0) or 0,
        "recovery_max_attempts": adi_manager.recovery_limit(project.id),
        "recovery_message": getattr(project, "recovery_message", "") or "",
            "workspace": workspace_status.get("workspace", {}),
            "recent_events": recent_events,
        },
    )


@app.get("/projects/{project_id}/revision/{revision_id}", response_class=HTMLResponse)
async def revision_review_view(
    request: Request,
    project_id: str,
    revision_id: int,
    user: str = Depends(require_user),
) -> HTMLResponse:
    project = adi_manager.get_project(project_id)
    if not project:
        return HTMLResponse("<h1>Project not found</h1>", status_code=404)
    revision = adi_manager.get_revision(project_id, revision_id)
    if not revision:
        return HTMLResponse("<h1>Revision not found</h1>", status_code=404)
    return templates.TemplateResponse(
        request,
        "revision_review.html",
        {
            "user": user,
            "project": project,
            "revision": revision,
        },
    )


@app.post("/api/projects/{project_id}/revision/{revision_id}/confirm")
async def confirm_revision(
    project_id: str, revision_id: int, user: str = Depends(require_user)
) -> dict[str, Any]:
    revision = adi_manager.get_revision(project_id, revision_id)
    if not revision:
        return {"status": "error", "message": "not_found"}
    if revision.get("confirmed"):
        return {
            "status": "ok",
            "redirect_url": f"/projects/{project_id}#reflection-panel",
            "rebuild_status": "in_progress",
            "message": "Доработка уже утверждена",
        }
    updated = adi_manager.confirm_revision(project_id, revision_id)
    if not updated:
        return {"status": "error", "message": "not_found"}
    _log_event(project_id, "revision_confirmed", {"revision_id": revision_id}, actor=user)
    asyncio.create_task(_run_revision_rebuild(project_id, revision_id))
    return {
        "status": "ok",
        "redirect_url": f"/projects/{project_id}?rebuild=1#reflection-panel",
        "acceptance_status": updated.acceptance_status,
        "rebuild_status": "started",
        "message": "Доработка утверждена. Запущена пересборка и деплой…",
    }


@app.get("/api/projects/{project_id}/rebuild-status")
async def rebuild_status(
    project_id: str, _user: str = Depends(require_user)
) -> dict[str, Any]:
    project = adi_manager.get_project(project_id)
    if not project:
        return {"status": "error", "message": "not_found"}
    detail = adi_manager.get_project_detail(project_id)
    return {
        "status": "ok",
        "project_status": project.status,
        "rebuild_status": getattr(project, "rebuild_status", "") or "",
        "rebuild_phase": getattr(project, "rebuild_phase", "") or "",
        "deploy_status": getattr(project, "deploy_status", "") or "",
        "processing_status": getattr(project, "processing_status", "") or "",
        "recovery_status": getattr(project, "recovery_status", "") or "",
        "recovery_attempts": getattr(project, "recovery_attempts", 0) or 0,
        "recovery_max_attempts": adi_manager.recovery_limit(project_id),
        "recovery_message": getattr(project, "recovery_message", "") or "",
        "acceptance_status": project.acceptance_status,
        "pending_revision_id": project.pending_revision_id,
        "deliverable": detail.get("deliverable") if detail else None,
    }


@app.get("/workflow/{task_id}", response_class=HTMLResponse)
async def workflow_view(
    request: Request, task_id: str, user: str = Depends(require_user)
) -> HTMLResponse:
    record = tasks.get(task_id)
    if not record:
        return HTMLResponse("<h1>Task not found</h1>", status_code=404)
    return templates.TemplateResponse(
        request,
        "workflow.html",
        {
            "task_id": task_id,
            "task_text": record.task,
            "status": record.status,
            "phase": record.phase,
            "project_id": record.project_id,
            "project_name": record.project_name,
            "pending_gate": record.pending_gate,
            "human_in_loop": record.human_in_loop,
            "tz": record.tz,
            "discussion": record.discussion,
            "deliverable": record.deliverable,
            "user": user,
        },
    )


def _gate_document(record: TaskRecord, gate: str) -> str:
    if gate == "tz":
        if record.tz:
            return record.tz
        if record.project_id:
            path = adi_manager.project_path(record.project_id) / "spec" / "TZ.md"
            if path.exists():
                return path.read_text(encoding="utf-8")
        return ""
    if gate == "spec":
        return record.spec
    return ""


def generated_content_headers(prefix: str | None = None) -> dict[str, str]:
    # Generated pages must not inherit the control panel's origin or permissions.
    origin = f"https://{get_config().domain}"
    resource = origin + prefix if prefix else "'none'"
    return {
        "Content-Security-Policy": (
            "sandbox allow-scripts allow-forms; default-src 'none'; "
            f"script-src 'unsafe-inline' {resource}; style-src 'unsafe-inline' {resource}; "
            f"img-src data: blob: {resource}; font-src {resource}; "
            f"connect-src {resource}; form-action {resource}; base-uri 'none'; "
            "frame-ancestors 'self'"
        ),
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }


@app.get("/preview/{project_id}")
async def preview_web(
    project_id: str, user: str = Depends(require_user)
) -> Response:
    src = adi_manager.project_path(project_id) / "src"
    for name in ("index.html", "app.html", "main.html"):
        path = src / name
        if path.exists():
            return FileResponse(path, headers=generated_content_headers())
    sim = adi_manager.project_path(project_id) / "preview" / "timer-simulator.html"
    if sim.exists():
        return RedirectResponse(url=f"/preview/{project_id}/simulator", status_code=303)
    mockup = adi_manager.project_path(project_id) / "preview" / "mobile-mockup.html"
    if mockup.exists():
        return RedirectResponse(url=f"/preview/{project_id}/mobile", status_code=303)
    return HTMLResponse("<h1>Preview not available</h1><p>Нет index.html в src/</p>", status_code=404)


@app.get("/preview/{project_id}/simulator")
async def preview_simulator(
    project_id: str, user: str = Depends(require_user)
) -> Response:
    sim = adi_manager.project_path(project_id) / "preview" / "timer-simulator.html"
    if sim.exists():
        return FileResponse(sim, headers=generated_content_headers())
    return HTMLResponse("<h1>Симулятор не сгенерирован</h1>", status_code=404)


@app.get("/preview/{project_id}/mobile")
async def preview_mobile(
    project_id: str, user: str = Depends(require_user)
) -> Response:
    mockup = adi_manager.project_path(project_id) / "preview" / "mobile-mockup.html"
    if mockup.exists():
        return FileResponse(mockup, headers=generated_content_headers())
    return HTMLResponse("<h1>Mobile mockup not generated</h1>", status_code=404)


@app.get("/api/projects/{project_id}/expo-download")
async def download_expo_project(
    project_id: str, user: str = Depends(require_user)
) -> Response:
    from ade.core.deliverable import build_expo_zip

    project = adi_manager.get_project(project_id)
    if not project:
        return HTMLResponse("<h1>Project not found</h1>", status_code=404)

    project_path = adi_manager.project_path(project_id)
    zip_path = build_expo_zip(project_path, project.name)
    if not zip_path:
        return HTMLResponse(
            "<h1>Expo project not ready</h1><p>Сначала завершите генерацию мобильного проекта.</p>",
            status_code=404,
        )

    filename = f"{project.name.replace(' ', '-')}-expo.zip"
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
    )


_PROXY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
)


@app.api_route(
    "/run/{project_id}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
@app.api_route(
    "/run/{project_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def workspace_run_proxy(
    project_id: str,
    request: Request,
    path: str = "",
    _user: str = Depends(require_user),
) -> Response:
    """Reverse-proxy to the project's workspace container via shared Docker network."""
    import httpx

    upstream = deployer_service.workspace_upstream(project_id)
    if not upstream:
        return HTMLResponse(
            "<h1>Workspace недоступен</h1><p>Запустите Deploy или дождитесь готовности контейнера.</p>",
            status_code=502,
        )

    target = f"http://{upstream['host']}:{upstream['port']}/{path.lstrip('/')}"
    if request.url.query:
        target = f"{target}?{request.url.query}"

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in _PROXY_HOP_HEADERS | {"cookie", "authorization"}
    }
    headers["accept-encoding"] = "identity"

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=False) as client:
            upstream_resp = await client.request(
                request.method,
                target,
                headers=headers,
                content=await request.body(),
            )
    except httpx.HTTPError as exc:
        logger.warning("Workspace proxy failed for %s: %s", project_id, exc)
        return HTMLResponse(
            "<h1>Workspace недоступен</h1><p>Контейнер не отвечает. Попробуйте Deploy ещё раз.</p>",
            status_code=502,
        )

    response_headers = {
        key: value
        for key, value in upstream_resp.headers.items()
        if key.lower() not in _PROXY_HOP_HEADERS | {
            "set-cookie", "content-length", "content-encoding", "content-security-policy",
        }
    }
    location = response_headers.get("location")
    if location:
        if not location.startswith("/") or location.startswith("//"):
            raise HTTPException(status_code=502, detail="External workspace redirect blocked")
        response_headers["location"] = f"/run/{project_id}{location}"
    response_headers.update(generated_content_headers(f"/run/{project_id}/"))
    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=response_headers,
    )


ROLE_LABELS: dict[str, str] = {
    "supervisor": "Supervisor",
    "architect": "Architect",
    "coder": "Coder",
    "reviewer": "Reviewer",
    "tester": "Tester",
    "deployer": "Deployer",
}


@app.get("/team", response_class=HTMLResponse)
async def agent_team_page(request: Request, user: str = Depends(require_user)) -> HTMLResponse:
    team_config = build_team_payload(include_prompts=True)
    return templates.TemplateResponse(
        request,
        "agent_team.html",
        {
            "user": user,
            "team_config": team_config,
            "role_labels": ROLE_LABELS,
        },
    )


@app.get("/api/team")
async def get_team(_user: str = Depends(require_user)) -> dict[str, Any]:
    return build_team_payload()


@app.get("/api/team/config")
async def get_team_config(_user: str = Depends(require_user)) -> dict[str, Any]:
    payload = build_team_payload(include_prompts=True)
    payload["status"] = "ok"
    return payload


class AgentConfigUpdate(BaseModel):
    model: str | None = None
    prompt: str | None = None


class WorkflowPromptUpdate(BaseModel):
    prompt: str = Field(min_length=1)


@app.put("/api/team/agents/{role}")
async def update_team_agent(
    role: str,
    body: AgentConfigUpdate,
    user: str = Depends(require_user),
) -> dict[str, Any]:
    try:
        agent_role = AgentRole(role)
    except ValueError:
        return {"status": "error", "message": "invalid_role"}
    if body.model is not None:
        model = body.model.strip()
        if not model:
            return {"status": "error", "message": "model_required"}
        team_manager.set_model(agent_role, model)
    if body.prompt is not None:
        team_manager.write_role_prompt(agent_role, body.prompt)
    reload_runtime_team()
    logger.info("Team agent updated: %s by %s", role, user)
    cfg = team.get(agent_role)
    return {
        "status": "ok",
        "role": role,
        "model": cfg.model,
        "customized": team_manager.is_role_customized(agent_role),
    }


@app.put("/api/team/workflows/{name}")
async def update_workflow_prompt(
    name: str,
    body: WorkflowPromptUpdate,
    user: str = Depends(require_user),
) -> dict[str, Any]:
    from ade.core.team_config import WORKFLOW_PROMPT_NAMES

    if name not in WORKFLOW_PROMPT_NAMES:
        return {"status": "error", "message": "invalid_workflow_prompt"}
    team_manager.write_workflow_prompt(name, body.prompt)
    reload_runtime_team()
    return {"status": "ok", "name": name}


@app.post("/api/team/reset")
async def reset_team_config(user: str = Depends(require_user)) -> dict[str, Any]:
    team_manager.reset_to_defaults()
    reload_runtime_team()
    logger.info("Team config reset by %s", user)
    return {"status": "ok", "message": "Настройки команды сброшены к значениям по умолчанию"}


@app.get("/api/projects")
async def list_projects_api(_user: str = Depends(require_user)) -> list[dict[str, Any]]:
    return [p.to_dict() for p in adi_manager.list_projects()]


@app.get("/api/projects/{project_id}")
async def get_project_api(project_id: str, _user: str = Depends(require_user)) -> dict[str, Any]:
    project = adi_manager.get_project(project_id)
    if not project:
        return {"error": "not_found"}
    return project.to_dict()


def _task_status_for_project(project_id: str) -> str:
    for record in tasks.values():
        if record.project_id == project_id:
            return record.status
    return ""


@app.get("/api/projects/{project_id}/delete-eligibility")
async def delete_eligibility(
    project_id: str, _user: str = Depends(require_user)
) -> dict[str, Any]:
    project = adi_manager.get_project(project_id)
    if not project:
        return {"status": "error", "message": "not_found", "can_delete": False}
    block = adi_manager.get_delete_block_reason(
        project_id, task_status=_task_status_for_project(project_id)
    )
    return {
        "status": "ok",
        "can_delete": block is None,
        "block_reason": block,
        "project_name": project.name,
    }


@app.post("/api/projects/{project_id}/duplicate")
async def duplicate_project(
    project_id: str, user: str = Depends(require_user)
) -> dict[str, Any]:
    source = adi_manager.get_project(project_id)
    if not source:
        return {"status": "error", "message": "not_found"}

    result = adi_manager.duplicate_project(project_id)
    if result.get("status") != "ok":
        return result

    new_id = result["project_id"]
    _log_event(
        new_id,
        "project_duplicated",
        {"name": result["name"], "cloned_from": project_id, "source_name": source.name},
        actor=user,
    )
    return {
        **result,
        "message": f"Создан дубликат «{result['name']}»",
    }


@app.delete("/api/projects/{project_id}")
async def delete_project(
    project_id: str,
    body: DeleteProjectRequest,
    _user: str = Depends(require_user),
) -> dict[str, Any]:
    project = adi_manager.get_project(project_id)
    if not project:
        return {"status": "error", "message": "not_found"}
    if body.confirm_name.strip() != project.name.strip():
        return {"status": "error", "message": "confirm_name_mismatch"}

    task_status = _task_status_for_project(project_id)
    _log_event(project_id, "project_delete_requested", {"name": project.name}, actor=_user)
    result = adi_manager.delete_project(project_id, task_status=task_status)
    if result.get("status") != "ok":
        return result
    _log_event(project_id, "project_deleted", {"name": project.name}, actor=_user)

    task_ids = [tid for tid, rec in tasks.items() if rec.project_id == project_id]
    for tid in task_ids:
        approval_gate.clear_task(tid)
        tasks.pop(tid, None)

    return {
        "status": "ok",
        "project_id": project_id,
        "redirect_url": "/dashboard",
        "message": f"Проект «{project.name}» удалён",
    }


@app.post("/api/projects/{project_id}/deploy")
async def deploy_project(
    project_id: str, user: str = Depends(require_user)
) -> dict[str, Any]:
    project = adi_manager.get_project(project_id)
    if not project:
        return {"status": "error", "message": "not_found"}
    if project.status == "rebuilding":
        return {"status": "error", "message": "rebuild_in_progress"}

    try:
        result = await asyncio.to_thread(
            deployer_service.deploy, project_id, use_agent=True
        )
    except Exception as exc:
        logger.exception("Deploy failed for %s", project_id)
        return {
            "status": "error",
            "message": "deploy_failed",
            "detail": str(exc)[:500],
        }

    if result.get("status") == "ok":
        _log_event(
            project_id,
            "deployed",
            {"workspace": result.get("workspace", {})},
            actor=user,
        )
    else:
        _log_event(
            project_id,
            "deploy_failed",
            {"detail": result.get("detail") or result.get("message")},
            actor=user,
        )
    return result


@app.get("/api/projects/{project_id}/status")
async def project_status(
    project_id: str, _user: str = Depends(require_user)
) -> dict[str, Any]:
    project = adi_manager.get_project(project_id)
    if not project:
        return {"status": "error", "message": "not_found"}
    ws = deployer_service.get_workspace_status(project_id)
    manifest = adi_manager._read_manifest(project_id)
    project_data = project.to_dict()
    project_data["deploy_error"] = manifest.get("deploy_error", "")
    project_data["workspace_mode"] = manifest.get("workspace_mode", "")
    return {
        "status": "ok",
        "project": project_data,
        "workspace": ws.get("workspace", {}),
        "events": event_store.list_events(project_id, limit=20),
    }


@app.post("/api/projects/{project_id}/accept")
async def accept_project(
    project_id: str, _user: str = Depends(require_user)
) -> dict[str, Any]:
    project = adi_manager.get_project(project_id)
    if not project:
        return {"status": "error", "message": "not_found"}
    if project.status == "rebuilding":
        return {"status": "error", "message": "rebuild_in_progress"}
    if project.status not in ("completed", "spec_ready", "code_ready"):
        return {"status": "error", "message": "project_not_ready"}
    updated = adi_manager.accept_project(project_id)
    _log_event(project_id, "project_accepted", actor=_user)
    return {
        "status": "ok",
        "acceptance_status": updated.acceptance_status if updated else "accepted",
        "accepted_at": updated.accepted_at if updated else None,
    }


@app.post("/api/projects/{project_id}/revise")
async def revise_project(
    project_id: str,
    body: ReflectionFeedbackRequest,
    _user: str = Depends(require_user),
) -> dict[str, Any]:
    adi_manager.ensure_pending_revision_record(project_id)
    project = adi_manager.get_project(project_id)
    if not project:
        return {"status": "error", "message": "not_found"}
    if project.pending_revision_id:
        rev_id = project.pending_revision_id
        return {
            "status": "error",
            "message": "pending_review",
            "redirect_url": f"/projects/{project_id}/revision/{rev_id}",
        }

    detail = adi_manager.get_project_detail(project_id)
    if not detail:
        return {"status": "error", "message": "not_found"}

    adi_manager.start_revision(project_id, body.feedback)
    adi_manager.set_processing_status(project_id, "architect_revising")
    try:
        new_tz, new_spec = await asyncio.to_thread(
            revise_tz_and_spec_from_feedback,
            team,
            project.idea,
            detail.get("tz", ""),
            detail["spec"],
            detail.get("review", ""),
            body.feedback,
        )
        old_tz = detail.get("tz", "")
        old_spec = detail["spec"]
        tz_sections = compare_sections(old_tz, new_tz)
        spec_sections = compare_sections(old_spec, new_spec)
        summary = summarize_changes(tz_sections, spec_sections)

        adi_manager.write_tz(project_id, new_tz, update_status=False)
        adi_manager.write_spec(project_id, new_spec, update_status=False)
        rev_id = adi_manager.save_revision_record(
            project_id,
            feedback=body.feedback,
            old_tz=old_tz,
            new_tz=new_tz,
            old_spec=old_spec,
            new_spec=new_spec,
            tz_sections=tz_sections,
            spec_sections=spec_sections,
            summary=summary,
        )
        updated = adi_manager.complete_revision(project_id)
        return {
            "status": "ok",
            "revision_id": rev_id,
            "redirect_url": f"/projects/{project_id}/revision/{rev_id}",
            "summary": summary,
            "acceptance_status": updated.acceptance_status if updated else "pending_review",
            "revision_count": updated.revision_count if updated else 0,
            "message": "ТЗ и Spec обновлены. Просмотрите изменения.",
        }
    except Exception as exc:
        logger.exception("Revise failed for %s", project_id)
        adi_manager.fail_rebuild(project_id, str(exc))
        return {"status": "error", "message": str(exc)}
    finally:
        adi_manager.clear_processing_status(project_id)


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str, _user: str = Depends(require_user)) -> dict[str, Any]:
    record = tasks.get(task_id)
    if not record:
        return {"status": "error", "message": "task_not_found"}
    return {
        "status": "ok",
        "id": record.id,
        "task": record.task,
        "summary": record.summary,
        "workflow_status": record.status,
        "phase": record.phase,
        "project_id": record.project_id,
        "pending_gate": record.pending_gate,
        "deliverable": record.deliverable,
        "error": record.error,
    }


@app.get("/api/tasks")
async def list_tasks(_user: str = Depends(require_user)) -> list[dict[str, str]]:
    return [
        {
            "id": t.id,
            "task": t.summary,
            "status": t.status,
            "phase": t.phase,
            "workflow": t.workflow,
            "project_id": t.project_id,
            "pending_gate": t.pending_gate,
            "created_at": t.created_at,
        }
        for t in sorted(tasks.values(), key=lambda x: x.created_at, reverse=True)
    ]


@app.post("/api/tasks", response_model=TaskResponse)
async def create_task_api(body: TaskRequest, _user: str = Depends(require_user)) -> TaskResponse:
    task_id = str(uuid.uuid4())
    project_id = ""
    project_name = body.project_name.strip() or body.task[:60].strip()
    if body.workflow == "dev_cycle":
        project_id = str(uuid.uuid4())
        adi_manager.bootstrap(
            project_id,
            project_name,
            body.task,
            task_id=task_id,
        )
        _log_event(
            project_id,
            "project_created",
            {"name": project_name, "task_id": task_id},
            actor=_user,
        )
    tasks[task_id] = TaskRecord(
        id=task_id,
        task=body.task,
        workflow=body.workflow,
        project_id=project_id,
        project_name=project_name,
        human_in_loop=body.human_in_loop,
    )
    asyncio.create_task(
        _dispatch_task(
            task_id,
            body.task,
            body.workflow,
            body.max_iterations,
            project_id=project_id,
            human_in_loop=body.human_in_loop,
        )
    )
    return TaskResponse(
        task_id=task_id,
        status="accepted",
        message="Task queued; subscribe via WebSocket /ws",
    )


@app.post("/api/tasks/{task_id}/approve")
async def approve_task_gate(
    task_id: str, body: ApprovalRequest, _user: str = Depends(require_user)
) -> dict[str, str]:
    record = tasks.get(task_id)
    if not record:
        return {"status": "error", "message": "task_not_found"}
    if not approval_gate.approve(task_id, body.gate, body.comment):
        return {"status": "error", "message": "gate_not_found"}
    gate_events = {
        "idea": "idea_approved",
        "tz": "tz_approved",
        "spec": "spec_approved",
        "code": "code_approved",
    }
    if record.project_id and body.gate in gate_events:
        _log_event(
            record.project_id,
            gate_events[body.gate],
            {"gate": body.gate, "comment": body.comment},
            actor=_user,
        )
    return {"status": "ok", "gate": body.gate, "action": "approved"}


@app.post("/api/tasks/{task_id}/reject")
async def reject_task_gate(
    task_id: str, body: ApprovalRequest, _user: str = Depends(require_user)
) -> dict[str, str]:
    record = tasks.get(task_id)
    if not record:
        return {"status": "error", "message": "task_not_found"}
    if not approval_gate.reject(task_id, body.gate, body.comment):
        return {"status": "error", "message": "gate_not_found"}
    return {"status": "ok", "gate": body.gate, "action": "rejected"}


@app.get("/api/tasks/{task_id}/sections")
async def get_task_sections(
    task_id: str, gate: str, _user: str = Depends(require_user)
) -> dict[str, Any]:
    record = tasks.get(task_id)
    if not record:
        return {"error": "task_not_found"}
    if gate not in ("tz", "spec"):
        return {"error": "invalid_gate"}
    document = _gate_document(record, gate)
    return {"gate": gate, "sections": parse_sections(document)}


@app.post("/api/tasks/{task_id}/discuss")
async def discuss_task_idea(
    task_id: str, body: DiscussRequest, _user: str = Depends(require_user)
) -> dict[str, Any]:
    record = tasks.get(task_id)
    if not record:
        return {"status": "error", "message": "task_not_found"}
    if record.pending_gate != "idea":
        return {"status": "error", "message": "not_in_idea_phase"}

    record.discussion.append(
        {"role": "user", "content": body.message, "ts": datetime.now(UTC).isoformat()}
    )
    reply = await asyncio.to_thread(
        discuss_idea, team, record.task, record.discussion[:-1], body.message
    )
    record.discussion.append(
        {"role": "architect", "content": reply, "ts": datetime.now(UTC).isoformat()}
    )
    await manager.broadcast(
        {
            "event": "discussion_message",
            "task_id": task_id,
            "role": "architect",
            "content": reply,
        },
        task_id,
    )
    return {"status": "ok", "reply": reply}


@app.post("/api/tasks/{task_id}/revise-section")
async def revise_task_section(
    task_id: str, body: ReviseSectionRequest, _user: str = Depends(require_user)
) -> dict[str, Any]:
    record = tasks.get(task_id)
    if not record:
        return {"status": "error", "message": "task_not_found"}
    if record.pending_gate != body.gate:
        return {"status": "error", "message": "gate_mismatch"}

    document = _gate_document(record, body.gate)
    if not document:
        return {"status": "error", "message": "document_empty"}

    updated, section = await asyncio.to_thread(
        revise_document_section,
        team,
        body.gate,
        document,
        body.section_id,
        body.comment,
        record.task,
    )
    if section is None:
        return {"status": "error", "message": "section_not_found"}

    if body.gate == "tz":
        record.tz = updated
        if record.project_id:
            adi_manager.write_tz(record.project_id, updated)
    else:
        record.spec = updated
        if record.project_id:
            adi_manager.write_spec(record.project_id, updated)

    await manager.broadcast(
        {
            "event": "document_updated",
            "task_id": task_id,
            "gate": body.gate,
            "section": section,
            "document": updated[:4000],
        },
        task_id,
    )
    return {"status": "ok", "gate": body.gate, "section": section, "sections": parse_sections(updated)}


@app.get("/", response_class=HTMLResponse)
async def index() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    if not websocket_authenticated(websocket):
        await websocket.close(code=4401, reason="Unauthorized")
        return
    await manager.connect(websocket)
    await websocket.send_json({"event": "connected", "version": __version__})
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if "subscribe" in msg:
                    manager.subscribe(msg["subscribe"], websocket)
                    await websocket.send_json(
                        {"event": "subscribed", "task_id": msg["subscribe"]}
                    )
                else:
                    await websocket.send_json({"event": "echo", "data": data})
            except json.JSONDecodeError:
                await websocket.send_json({"event": "echo", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/projects/{project_id}/engineering")
async def engineering_status(project_id: str, _user: str = Depends(require_user)) -> dict:
    project = adi_manager.get_project(project_id)
    if not project:
        return {"status": "error", "message": "not_found"}
    manifest = adi_manager._read_manifest(project_id)
    return {"status": "ok", "active_release_id": manifest.get("active_release_id"),
            "previous_release_id": manifest.get("previous_release_id"),
            "quality_status": manifest.get("quality_status", "not_checked"),
            "releases": ReleaseService(adi_manager).list_releases(project_id)}


@app.post("/api/projects/{project_id}/verify")
async def verify_project(project_id: str, user: str = Depends(require_user)) -> dict:
    try:
        report = await asyncio.to_thread(ReleaseService(adi_manager).prepare, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)[:500]) from exc
    _log_event(project_id, "release_verified", {"release_id": report['release_id'],
               "passed": report['passed']}, actor=user)
    return report


@app.post("/api/projects/{project_id}/rollback")
async def rollback_project(project_id: str, user: str = Depends(require_user)) -> dict:
    result = await asyncio.to_thread(deployer_service.rollback, project_id)
    _log_event(project_id, "release_rollback", result, actor=user)
    return result


class LessonRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    project_id: str
    release_id: str


@app.get("/api/knowledge/lessons")
async def list_lessons(_user: str = Depends(require_user)) -> list[dict]:
    return LessonStore().list()


@app.post("/api/knowledge/lessons")
async def propose_lesson(body: LessonRequest, _user: str = Depends(require_user)) -> dict:
    snapshot = ReleaseService(adi_manager).verify(body.project_id, body.release_id)
    report = json.loads((snapshot / "verification.json").read_text())
    lesson_id = LessonStore().propose(body.title, body.body,
        {"project_id": body.project_id, "release_id": body.release_id,
         "verification_passed": report['passed']})
    return {"status": "ok", "id": lesson_id, "approval_required": True}


@app.post("/api/knowledge/lessons/{lesson_id}/approve")
async def approve_lesson(lesson_id: int, user: str = Depends(require_user)) -> dict:
    return {"status": "ok" if LessonStore().approve(lesson_id, user) else "error"}
