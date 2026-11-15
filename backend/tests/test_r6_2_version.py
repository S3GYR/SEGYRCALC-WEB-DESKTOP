"""R6.2 version metadata regression tests for DEF-VER-01."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = "0.8.0-r6.2"


def test_python_version_is_valid_pep440_mapping() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == "0.8.0+r6.2"


def test_frontend_and_lock_versions_are_aligned() -> None:
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))

    assert package["version"] == CANONICAL
    assert lock["version"] == CANONICAL
    assert lock["packages"][""]["version"] == CANONICAL
    assert lock["name"] == package["name"]
    assert lock["packages"][""]["name"] == package["name"]


def test_installer_and_documentation_use_r6_2() -> None:
    installer = (ROOT / "installer" / "SEGYRCALC.iss").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert '#define MyAppVersion "0.8.0-r6.2"' in installer
    assert "VersionInfoVersion=0.8.0.2" in installer
    assert "VersionInfoProductVersion=0.8.0-r6.2" in installer
    assert "0.8.0-r6.2" in readme
    assert "0.8.0-r6.2" in changelog


def test_ui_version_labels_are_r6_2() -> None:
    sidebar = (ROOT / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(
        encoding="utf-8"
    )
    settings = (ROOT / "frontend" / "src" / "screens" / "SettingsScreen.tsx").read_text(
        encoding="utf-8"
    )
    assert "0.8.0-r6.2" in sidebar
    assert "0.8.0-r6.2" in settings
    assert "v0.7.1" not in sidebar
    assert "v0.7.1" not in settings
