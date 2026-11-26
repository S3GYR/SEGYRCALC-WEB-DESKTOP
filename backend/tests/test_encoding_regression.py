from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".css", ".html", ".json"}
PATTERNS = (
    chr(0xC3) + chr(0xA8),
    chr(0xC3) + chr(0xA9),
    chr(0xC3) + chr(0xAA),
    chr(0xC3) + chr(0xA7),
    chr(0xC2) + chr(0xAB),
    chr(0xC2) + chr(0xBB),
    chr(0xE2) + chr(0x20AC) + chr(0x201D),
    chr(0xE2) + chr(0x20AC) + chr(0xA6),
    chr(0xE2) + chr(0x20AC) + chr(0x2122),
    chr(0xFFFD),
)


def _text_files() -> list[Path]:
    paths: list[Path] = []
    for base in (ROOT / "backend", ROOT / "frontend" / "src", ROOT / "scripts"):
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if "node_modules" in path.parts or "dist" in path.parts:
                continue
            paths.append(path)
    paths.append(ROOT / "frontend" / "index.html")
    return paths


def test_application_sources_are_utf8_and_have_no_mojibake() -> None:
    failures: list[str] = []
    for path in _text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            failures.append(f"{path}: invalid UTF-8: {exc}")
            continue
        for pattern in PATTERNS:
            if pattern in text:
                failures.append(f"{path}: contains U+{ord(pattern[0]):04X} sequence")
    assert not failures, "\n".join(failures)


def test_expected_french_labels_are_present() -> None:
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    clients = (ROOT / "frontend" / "src" / "screens" / "ClientsScreen.tsx").read_text(
        encoding="utf-8"
    )
    distribution = (ROOT / "backend" / "distribution.py").read_text(encoding="utf-8")
    assert "Paramètres" in app
    assert "Architecture électrique" in app
    assert "Bibliothèque" in app
    assert "Téléphone" in clients
    assert "Référentiel local — WEB-08" in clients
    assert "départ monophasé" in distribution


def test_html_declares_utf8_and_clean_title() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<meta charset="UTF-8" />' in html
    assert "SEGYRCALC BETA — Bilan de puissance" in html


def test_http_assets_declare_utf8(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from backend.main import create_app
    from backend.project_commands import CommandProjectStore

    store = CommandProjectStore(root=tmp_path / "projects")
    app = create_app("encoding-test-token", allow_test_host=True, project_store=store)
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "charset=utf-8" in page.headers["content-type"]
        assets = sorted((ROOT / "frontend" / "dist" / "assets").glob("index-*.js"))
        assert assets
        asset = client.get(f"/assets/{assets[0].name}")
        assert asset.status_code == 200
        assert "charset=utf-8" in asset.headers["content-type"]
