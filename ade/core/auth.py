"""Session-based authentication for ADE v4."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException, Request, WebSocket
from starlette.responses import JSONResponse, RedirectResponse, Response

from ade.core.config import get_config

SESSION_USER_KEY = "user"
SESSION_ROLE_KEY = "role"

PUBLIC_PATHS = frozenset({
    "/health",
    "/login",
    "/auth/login",
    "/openapi.json",
    "/docs",
    "/redoc",
})

PUBLIC_PREFIXES = ("/docs/", "/redoc/", "/static/")


def verify_credentials(username: str, password: str) -> bool:
    config = get_config()
    user_ok = secrets.compare_digest(username.strip(), config.admin_username)
    pass_ok = secrets.compare_digest(password, config.admin_password)
    return user_ok and pass_ok


def get_current_user(request: Request) -> str | None:
    return request.session.get(SESSION_USER_KEY)


def login_user(request: Request, username: str) -> None:
    request.session[SESSION_USER_KEY] = username
    request.session[SESSION_ROLE_KEY] = "admin"


def logout_user(request: Request) -> None:
    request.session.clear()


def require_user(request: Request) -> str:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def is_public_path(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return path_is_api(request.url.path) or "application/json" in accept


def path_is_api(path: str) -> bool:
    return path.startswith("/api/")


async def auth_middleware(request: Request, call_next) -> Response:
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if is_public_path(path):
        return await call_next(request)

    if get_current_user(request):
        return await call_next(request)

    if wants_json(request):
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    next_url = path
    if request.url.query:
        next_url = f"{path}?{request.url.query}"
    return RedirectResponse(url=f"/login?next={next_url}", status_code=303)


def websocket_authenticated(websocket: WebSocket) -> bool:
    session: dict[str, Any] = websocket.scope.get("session") or {}
    return bool(session.get(SESSION_USER_KEY))