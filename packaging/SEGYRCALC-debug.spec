# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parents[0]
ENGINE = ROOT.parent.parent / "SEGYRCALC-V1.5-UI-ERGONOMIE-01" / "worktree"
FIXTURE = ENGINE / "examples" / "recette-business-acceptance-v1.3.json"

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("webview")
    + [
        "backend.desktop",
        "backend.main",
        "backend.engine_adapter",
        "backend.project_commands",
        "backend.project_payload",
        "backend.project_store",
        "backend.reporting",
        "backend.report_pdf",
        "backend.report_xlsx",
        "backend.report_csv",
        "backend.runtime_paths",
        "sqlite3",
        "_sqlite3",
    ]
)
datas = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "frontend" / "public" / "assets"), "frontend/public/assets"),
    (str(ENGINE / "src"), "engine_src"),
    (str(FIXTURE), "engine_fixtures"),
    (str(ROOT / "packaging" / "sample_projects"), "sample_projects"),
] + collect_data_files("webview")

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytestqt", "PySide6", "playwright"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SEGYRCALC-debug",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    icon=str(ROOT / "frontend" / "public" / "assets" / "segyrcalc.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SEGYRCALC-debug",
)
