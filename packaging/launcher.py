"""Frozen entry point for the isolated SEGYRCALC Windows candidate."""

from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


def _configure_runtime() -> Path:
    bundle = _bundle_root()
    local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    # BETA uses a dedicated data root and never writes to the stable app data.
    beta_override = os.environ.get("SEGYR_BETA_DATA_ROOT") or os.environ.get(
        "SEGYR_RECETTE_DATA_ROOT"
    )
    data_root = (
        Path(beta_override)
        if beta_override
        else Path(local_appdata) / "SEGYR Technologies" / "SEGYRCALC-BETA"
    )
    projects_root = data_root / "Projects"
    exports_root = data_root / "Exports"
    logs_root = data_root / "Logs"
    for path in (data_root, projects_root, exports_root, logs_root):
        path.mkdir(parents=True, exist_ok=True)

    engine_src = bundle / "engine_src"
    fixture = bundle / "engine_fixtures" / "recette-business-acceptance-v1.3.json"
    sample = bundle / "sample_projects" / "web05-native-qualification.segyrcalc-web.json"
    os.environ["SEGYR_USER_DATA_ROOT"] = str(data_root)
    os.environ["SEGYR_PROJECTS_ROOT"] = str(projects_root)
    os.environ["SEGYR_EXPORTS_ROOT"] = str(exports_root)
    os.environ["SEGYR_LOGS_ROOT"] = str(logs_root)
    os.environ["SEGYR_ENGINE_SRC"] = str(engine_src)
    os.environ["SEGYR_PROJECT_FIXTURE"] = str(fixture)
    os.environ["SEGYR_SAMPLE_PROJECT"] = str(sample)
    os.environ["SEGYR_APP_CHANNEL"] = "BETA"

    # Keep the BETA build identity in a local startup log for support.
    try:
        metadata_path = bundle / "build_metadata" / "build-metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        (logs_root / "beta-startup.json").write_text(
            json.dumps(
                {
                    "channel": "BETA",
                    "application_version": metadata.get("application_version"),
                    "build_id": metadata.get("build_id"),
                    "build_git_commit": metadata.get("build_git_commit"),
                    "build_at": metadata.get("build_at"),
                    "engine_version": metadata.get("engine_version"),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass

    for path in (bundle, engine_src):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    return data_root


def main() -> int:
    try:
        _configure_runtime()
        from backend.desktop import main as desktop_main

        return int(desktop_main())
    except Exception as exc:  # pragma: no cover - native startup guard
        message = f"SEGYRCALC BETA n'a pas pu démarrer.\n\n{exc}\n\n{traceback.format_exc()}"
        try:
            log = Path(tempfile.gettempdir()) / "segyrcalc-startup.log"
            log.write_text(message, encoding="utf-8")
        except Exception:
            pass
        print(message, file=sys.stderr)
        try:
            ctypes.windll.user32.MessageBoxW(None, message, "SEGYRCALC BETA", 0x10)
        except Exception:
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
