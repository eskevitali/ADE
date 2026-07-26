#!/usr/bin/env python3
"""Tests for session-based authentication."""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from ade.core.auth import verify_credentials
from ade.core.config import get_config
from ade.ui.main import app


def test_verify_credentials() -> None:
    config = get_config()
    assert verify_credentials(config.admin_username, config.admin_password)
    assert not verify_credentials(config.admin_username, "wrong")
    assert not verify_credentials("wrong@user.com", config.admin_password)
    print("[OK] Credential verification")


def test_public_routes() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/login").status_code == 200
    print("[OK] Public routes accessible")


def test_protected_routes_redirect() -> None:
    client = TestClient(app)
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")
    print("[OK] Protected routes redirect to login")


def test_login_flow() -> None:
    config = get_config()
    client = TestClient(app)
    response = client.post(
        "/auth/login",
        data={"username": config.admin_username, "password": config.admin_password, "next": "/dashboard"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert config.admin_username in dashboard.text

    api = client.get("/api/team")
    assert api.status_code == 200
    assert "team_count" in api.json()
    print("[OK] Login flow and session access")


def test_logout_flow() -> None:
    config = get_config()
    client = TestClient(app)
    client.post(
        "/auth/login",
        data={"username": config.admin_username, "password": config.admin_password},
        follow_redirects=True,
    )
    logout = client.post("/auth/logout", follow_redirects=False)
    assert logout.status_code == 303
    assert client.get("/dashboard", follow_redirects=False).status_code == 303
    print("[OK] Logout clears session")


def main() -> int:
    print("=== ADE v4 Auth Test ===\n")
    try:
        test_verify_credentials()
        test_public_routes()
        test_protected_routes_redirect()
        test_login_flow()
        test_logout_flow()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    print("\n=== All auth checks passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())