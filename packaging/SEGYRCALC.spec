# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parents[0]
ENGINE = Path(os.environ.get("SEGYR_ENGINE_ROOT", ROOT.parent.parent / "SEGYRCALC-V1.5-UI-ERGONOMIE-01" / "worktree")).resolve()
FIXTURE = ENGINE / "examples" / "recette-business-acceptance-v1.3.json"
FRONTEND_DIST = Path(os.environ.get("SEGYR_FRONTEND_DIST", ROOT / "frontend" / "dist")).resolve()
BUILD_METADATA = Path(os.environ.get("SEGYR_BUILD_METADATA", ROOT / "build-metadata.json")).resolve()
if not (FRONTEND_DIST / "index.html").is_file():
    raise SystemExit(f"Frontend dist introuvable: {FRONTEND_DIST}")
if not BUILD_METADATA.is_file():
    raise SystemExit(f"Metadonnees de build introuvables: {BUILD_METADATA}")

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("webview")
    + [
        "backend.desktop",
        "backend.main",
        "backend.client_store",
        "backend.client_v2",
        "backend.company_store",
        "backend.distribution",
        "backend.engine_adapter",
        "backend.project_commands",
        "backend.project_payload",
        "backend.project_store",
        "backend.reporting",
        "backend.report_pdf",
        "backend.report_xlsx",
        "backend.report_csv",
        "backend.runtime_paths",
        "calcelect.service_v11",
        "calcelect.service_v13",
        "calcelect.phase_service",
        "calcelect.clients",
        "calcelect.clients.errors",
        "calcelect.clients.logos",
        "calcelect.clients.models",
        "calcelect.clients.normalization",
        "calcelect.clients.paths",
        "calcelect.clients.repository",
        "calcelect.clients.service",
        "sqlite3",
        "_sqlite3",
    ]
)

datas = [
    (str(FRONTEND_DIST), "frontend/dist"),
    (str(BUILD_METADATA), "build_metadata"),
    (str(ROOT / "frontend" / "public" / "assets"), "frontend/public/assets"),
    (str(ENGINE / "src"), "engine_src"),
    (str(FIXTURE), "engine_fixtures"),
    (str(ROOT / "packaging" / "sample_projects"), "sample_projects"),
] + collect_data_files("webview")

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT), str(ENGINE / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "pytestqt",
        "PySide6",
        "playwright",
        "pymupdf",
        "fitz",
        "numpy",
        "mypy",
        "psutil",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SEGYRCALC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    name="SEGYRCALC",
)

