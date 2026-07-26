#!/usr/bin/env python3
"""Tests for Expo mobile scaffold (SDK 54)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ade.core.config import get_config
from ade.core.deliverable import (
    EXPO_SDK_MAJOR,
    _expo_needs_refresh,
    _expo_sdk_major,
    build_deliverable,
    build_expo_zip,
    ensure_expo_project,
    expo_zip_path,
    refresh_expo_project_if_stale,
)
import zipfile


def test_ensure_expo_project_creates_sdk54() -> None:
    config = get_config()
    tmp = config.projects_dir / "expo-scaffold-test"
    tmp.mkdir(parents=True, exist_ok=True)
    expo_dir = ensure_expo_project(tmp, "Я ТУТ", 'кнопка "Я ТУТ"')
    package_json = json.loads((expo_dir / "package.json").read_text(encoding="utf-8"))
    assert package_json["dependencies"]["expo"].startswith(f"~{EXPO_SDK_MAJOR}.")
    assert package_json["dependencies"]["react-native"] == "0.81.5"
    assert package_json["engines"]["node"] == ">=20.12.0"
    app_tsx = (expo_dir / "App.tsx").read_text(encoding="utf-8")
    assert "Я ТУТ" in app_tsx
    assert (expo_dir / "index.ts").exists()
    assert (expo_dir / "app.json").exists()
    print("[OK] ensure_expo_project creates SDK 54 scaffold")


def test_refresh_stale_expo() -> None:
    config = get_config()
    tmp = config.projects_dir / "expo-stale-test"
    expo_dir = tmp / "expo"
    expo_dir.mkdir(parents=True, exist_ok=True)
    (expo_dir / "package.json").write_text(
        json.dumps({"dependencies": {"expo": "~49.0.0"}}),
        encoding="utf-8",
    )
    assert _expo_sdk_major(expo_dir / "package.json") == 49
    assert _expo_needs_refresh(expo_dir) is True
    refresh_expo_project_if_stale(tmp, "Stale App", "")
    assert _expo_sdk_major(expo_dir / "package.json") == EXPO_SDK_MAJOR
    print("[OK] refresh_expo_project_if_stale upgrades legacy SDK")


def test_build_deliverable_expo_paths() -> None:
    config = get_config()
    tmp = config.projects_dir / "expo-deliverable-test"
    tmp.mkdir(parents=True, exist_ok=True)
    stale_zip = expo_zip_path(tmp)
    if stale_zip.exists():
        stale_zip.unlink()
    ensure_expo_project(tmp, "Mobile", "")
    deliverable = build_deliverable("expo-deliverable-test", "Mobile", "iOS app", "", "", tmp)
    assert deliverable["type"] == "mobile"
    assert deliverable.get("expo_download_url", "").endswith("/expo-download")
    assert deliverable.get("expo_download_label") == "Создать и скачать ZIP"
    assert "npm install" in deliverable["simulator_exports"][0]["command"]
    assert "projects/" not in deliverable["simulator_exports"][0]["command"]
    assert "Создать и скачать ZIP" in deliverable["instructions"]
    assert not expo_zip_path(tmp).exists()
    print("[OK] build_deliverable offers on-demand ZIP without prebuilding archive")


def test_expo_zip_archive() -> None:
    config = get_config()
    tmp = config.projects_dir / "expo-zip-test"
    tmp.mkdir(parents=True, exist_ok=True)
    stale_zip = expo_zip_path(tmp)
    if stale_zip.exists():
        stale_zip.unlink()
    ensure_expo_project(tmp, "Zip Test", "")
    assert not expo_zip_path(tmp).exists()
    zip_path = build_expo_zip(tmp, "Zip Test")
    assert zip_path is not None
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "package.json" in names
    assert "LAUNCH.md" in names
    assert "App.tsx" in names
    assert not any(n.startswith("node_modules/") for n in names)
    print("[OK] build_expo_zip packs launch guide without node_modules")


def main() -> int:
    print("=== Expo scaffold tests ===\n")
    try:
        test_ensure_expo_project_creates_sdk54()
        test_refresh_stale_expo()
        test_build_deliverable_expo_paths()
        test_expo_zip_archive()
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        raise
    print("\n=== All expo scaffold tests passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())