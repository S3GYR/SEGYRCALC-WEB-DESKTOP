"""BETA version metadata regression tests."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = "0.9.0-beta.1"
PEP440 = "0.9.0b1"


def test_python_version_is_valid_pep440_mapping() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == PEP440


def test_frontend_and_lock_versions_are_aligned() -> None:
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))

    assert package["version"] == CANONICAL
    assert lock["version"] == CANONICAL
    assert lock["packages"][""]["version"] == CANONICAL
    assert lock["name"] == package["name"]
    assert lock["packages"][""]["name"] == package["name"]


def test_beta_installer_and_documentation_use_beta_version() -> None:
    installer = (ROOT / "installer" / "SEGYRCALC-BETA.iss").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert '#define MyAppVersion "0.9.0-beta.1"' in installer
    assert "VersionInfoVersion=0.9.0.1" in installer
    assert "VersionInfoProductVersion=0.9.0" in installer
    assert CANONICAL in readme
    assert CANONICAL in changelog


def test_ui_version_labels_are_beta() -> None:
    sidebar = (ROOT / "frontend" / "src" / "components" / "Sidebar.tsx").read_text(
        encoding="utf-8"
    )
    settings = (ROOT / "frontend" / "src" / "screens" / "SettingsScreen.tsx").read_text(
        encoding="utf-8"
    )
    assert CANONICAL in sidebar
    assert CANONICAL in settings
    assert "0.8.0-r6.2" not in sidebar
    assert "0.8.0-r6.2" not in settings
    assert "v0.7.1" not in sidebar
    assert "v0.7.1" not in settings
