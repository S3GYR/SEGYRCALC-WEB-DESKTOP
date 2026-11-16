from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.desktop import _print_json
from backend.main import create_app
from backend.project_commands import CommandProjectStore
from backend.project_store import ProjectStoreError
from backend.reporting import ReportConfig, ReportService

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "packaging" / "sample_projects" / "web05-native-qualification.segyrcalc-web.json"


def _symbol_project(tmp_path: Path) -> Path:
    data = json.loads(SAMPLE.read_text(encoding="utf-8-sig"))
    electrical = data["calcelect_v14"]["project"]["electrical"]
    electrical["name"] = "Électricité — √ ≤ ≥ Ω Δ φ × ± ° ² ³ µ œ"
    electrical["loads"][0]["designation"] = "Récepteur √ ≤ ≥ Ω Δ φ"
    target = tmp_path / "symbols.segyrcalc-web.json"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def test_pdf_preserves_math_glyphs(tmp_path: Path) -> None:
    target = _symbol_project(tmp_path)
    store = CommandProjectStore(root=tmp_path)
    store.open(target)
    service = ReportService(root=tmp_path / "exports")
    config = ReportConfig(
        title="Rapport √ ≤ ≥ Ω Δ φ",
        sections=[
            "cover", "general", "summary", "boards", "feeders", "receivers",
            "coefficients", "phases", "assumptions", "traceability",
        ],
        orientation="portrait",
        decimals=2,
        units="auto",
        include_assumptions=True,
        include_traceability=True,
    )
    preview = service.preview(store, config)
    pdf_path = tmp_path / "report.pdf"
    service.export(preview["snapshot"]["snapshot_id"], "pdf", pdf_path, overwrite=True)
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages)
    for character in "√≤≥ΩΔφ×±°²³µœé":
        assert character in text, f"missing {character!r} in PDF text"
    assert "\x00" not in text
    assert len(PdfReader(str(pdf_path)).pages) >= 2


def test_powershell_launcher_has_utf8_bom() -> None:
    raw = (ROOT / "scripts" / "start-segyrcalc-dev.ps1").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")


def test_desktop_json_output_falls_back_on_cp1252() -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")
    with redirect_stdout(stream):
        _print_json({"value": "Ω √ ≤ ≥"})
        stream.flush()
    payload = json.loads(buffer.getvalue().decode("ascii"))
    assert payload["value"] == "Ω √ ≤ ≥"


def test_api_host_error_is_accented(tmp_path: Path) -> None:
    app = create_app(
        "encoding-remediation-token",
        allow_test_host=True,
        project_store=CommandProjectStore(root=tmp_path / "projects"),
    )
    with TestClient(app) as client:
        response = client.get("/api/project", headers={"Host": "evil.example"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Hôte non autorisé."


def test_store_missing_messages_are_accented(tmp_path: Path) -> None:
    target = _symbol_project(tmp_path)
    store = CommandProjectStore(root=tmp_path)
    store.open(target)
    revision = store._payload()["state"]["revision"]
    with pytest.raises(ProjectStoreError) as missing_load:
        store.update_load({"load_id": "NOPE", "expected_revision": revision})
    assert missing_load.value.message == "Récepteur introuvable."
    existing_load = store._payload()["loads"][0]["id"]
    with pytest.raises(ProjectStoreError) as missing_feeder:
        store.update_load({"load_id": existing_load, "feeder_id": "NOPE", "expected_revision": revision})
    assert missing_feeder.value.message == "Départ introuvable."
