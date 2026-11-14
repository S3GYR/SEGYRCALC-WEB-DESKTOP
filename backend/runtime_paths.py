"""Runtime paths shared by the development build and the frozen package."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def data_root() -> Path:
    configured = os.environ.get("SEGYR_USER_DATA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return PACKAGE_ROOT


def projects_root() -> Path:
    configured = os.environ.get("SEGYR_PROJECTS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return data_root() / "qualification-projects"


def exports_root() -> Path:
    configured = os.environ.get("SEGYR_EXPORTS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return data_root() / "qualification-exports"


def logs_root() -> Path:
    configured = os.environ.get("SEGYR_LOGS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return data_root() / "logs"


def is_packaged() -> bool:
    return bool(os.environ.get("SEGYR_USER_DATA_ROOT"))
