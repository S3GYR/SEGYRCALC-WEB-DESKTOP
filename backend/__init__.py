"""SEGYRCALC WEB-03 isolated backend."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ENGINE_SRC = (
    _PROJECT_ROOT.parent.parent / "SEGYRCALC-V1.5-UI-ERGONOMIE-01" / "worktree" / "src"
)
_ENGINE_SRC = (
    Path(os.environ.get("SEGYR_ENGINE_SRC", str(_DEFAULT_ENGINE_SRC))).expanduser().resolve()
)
if str(_ENGINE_SRC) not in sys.path:
    sys.path.insert(0, str(_ENGINE_SRC))
