from __future__ import annotations

import csv
import io
import shutil
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

from backend.project_commands import CommandProjectStore
from backend.reporting import ReportConfig, ReportService

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "packaging" / "sample_projects" / "web05-native-qualification.segyrcalc-web.json"
ENGINE_DISPLAY_NAME = "SEGYRCALC \u2013 Moteur de calcul \u00e9lectrique"
TECHNICAL_FACADE = "calcelect.service_v13.calculate_project_v13"


def _preview(tmp_path: Path):
    store = CommandProjectStore(root=tmp_path)
    sample = tmp_path / "sample.segyrcalc-web.json"
    shutil.copy2(SAMPLE, sample)
    store.open(sample)
    service = ReportService(root=tmp_path / "exports")
    config = ReportConfig(title="Rapport de qualification moteur")
    preview = service.preview(store, config)
    return service, preview


def test_pdf_xlsx_csv_use_user_facing_engine_name(tmp_path: Path) -> None:
    service, preview = _preview(tmp_path)
    snapshot_id = preview["snapshot"]["snapshot_id"]
    engine = preview["traceability"]["engine"]

    # The internal API payload keeps the technical identifier.
    assert engine["facade"] == TECHNICAL_FACADE
    assert engine["version"] == "1.3.0"
    assert engine["engine_source_sha256"]

    pdf_path = tmp_path / "report.pdf"
    service.export(snapshot_id, "pdf", pdf_path, overwrite=True)
    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages)
    assert ENGINE_DISPLAY_NAME in pdf_text
    assert TECHNICAL_FACADE not in pdf_text
    assert engine["version"] in pdf_text
    assert engine["engine_source_sha256"] in pdf_text
    assert "\x00" not in pdf_text

    xlsx_path = tmp_path / "report.xlsx"
    service.export(snapshot_id, "xlsx", xlsx_path, overwrite=True)
    workbook = load_workbook(xlsx_path, data_only=False)
    trace = workbook["Tra\u00e7abilit\u00e9"]
    rows = list(trace.iter_rows(values_only=True))
    engine_row = next(row for row in rows if row[0] == "Moteur")
    assert engine_row[1] == ENGINE_DISPLAY_NAME
    assert all(TECHNICAL_FACADE not in str(cell) for row in rows for cell in row)
    workbook.close()

    csv_dir = tmp_path / "csv"
    service.export(snapshot_id, "csv", csv_dir, overwrite=True)
    raw = (csv_dir / "tracabilite.csv").read_text(encoding="utf-8-sig")
    csv_rows = list(csv.reader(io.StringIO(raw), delimiter=";"))
    engine_csv = next(row for row in csv_rows if row[0] == "Moteur")
    assert engine_csv[1] == ENGINE_DISPLAY_NAME
    assert TECHNICAL_FACADE not in raw
