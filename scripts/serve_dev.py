"""Local-only server used for browser qualification captures (not production)."""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import create_app  # noqa: E402


def main() -> int:
    app = create_app("web02-browser-qualification")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
