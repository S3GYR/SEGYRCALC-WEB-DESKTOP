from __future__ import annotations

import csv
import hashlib
import io
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pypdf import PdfReader

from backend.main import create_app
from backend.project_commands import CommandProjectStore
from backend.reporting import ReportConfig, ReportService

TOKEN = "web06-test-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def client(tmp_path: Path) -> TestClient:
    store = CommandProjectStore(root=tmp_path / "projects")
    reports = ReportService(root=tmp_path / "exports")
    return TestClient(
        create_app(
            TOKEN,
            allow_test_host=True,
            project_store=store,
            report_service=reports,
        )
    )


def create_report_project(api: TestClient) -> dict[str, Any]:
    created = api.post(
        "/api/project/new",
        headers=AUTH,
        json={
            "name": "Rapport WEB-06 test",
            "reference": "WEB06-TEST",
            "client": "Client test",
            "site": "Site test",
            "address": "6 rue du Rapport",
            "author": "Qualification",
            "description": "Projet de test des exports",
            "observations": "Aucune",
            "revision": "A",
            "standard": "NF C 15-100",
            "network": "TRI",
            "voltage_v": "400",
            "has_neutral": True,
            "voltage_ln_v": "230",
        },
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    board = api.post(
        "/api/project/boards",
        headers=AUTH,
        json={
            "expected_revision": payload["state"]["revision"],
            "parent_board_id": payload["boards"][0]["id"],
            "designation": "Tableau divisionnaire test",
            "description": "",
            "has_neutral": True,
            "voltage_ln_v": "230",
        },
    )
    assert board.status_code == 200, board.text
    payload = board.json()
    divisionnaire = next(item for item in payload["boards"] if item["type"] == "DIVISIONNAIRE")
    feeder = api.post(
        "/api/project/feeders",
        headers=AUTH,
        json={
            "expected_revision": payload["state"]["revision"],
            "parent_board_id": divisionnaire["id"],
            "designation": "Départ éclairage",
            "description": "",
            "ks": "0.9",
            "phase": None,
            "has_neutral": True,
            "voltage_ln_v": "230",
        },
    )
    assert feeder.status_code == 200, feeder.text
    payload = feeder.json()
    feeder_id = next(item for item in payload["feeders"] if not item.get("downstream_board_id"))
    for index, phase in enumerate(("L1", "L2", "L3")):
        load = api.post(
            "/api/project/loads",
            headers=AUTH,
            json={
                "expected_revision": payload["state"]["revision"],
                "feeder_id": feeder_id["id"],
                "designation": f"Récepteur éclairage {index + 1}",
                "network": "MONO",
                "voltage_v": "230",
                "nominal_power": "1200",
                "power_unit": "W",
                "quantity": 2,
                "power_factor": "0.92",
                "ku": "0.8",
                "phase": phase,
            },
        )
        assert load.status_code == 200, load.text
        payload = load.json()
    return payload


def report_config(**overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "title": "Bilan de puissance — test WEB-06",
        "sections": [
            "cover",
            "general",
            "summary",
            "architecture",
            "boards",
            "feeders",
            "receivers",
            "coefficients",
            "phases",
            "assumptions",
            "traceability",
        ],
        "orientation": "portrait",
        "decimals": 2,
        "units": "auto",
        "include_assumptions": True,
        "include_traceability": True,
    }
    config.update(overrides)
    return config


def preview(api: TestClient, **overrides: object) -> dict[str, Any]:
    response = api.post(
        "/api/reports/preview",
        headers=AUTH,
        json={"config": report_config(**overrides)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_report_preview_uses_engine_values_and_snapshot(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        project = create_report_project(api)
        body = preview(api)
        assert body["snapshot"]["project_reference"] == "WEB06-TEST"
        assert body["snapshot"]["revision"] == project["state"]["revision"]
        assert body["snapshot"]["calculation_revision"] == project["state"]["revision"]
        assert len(body["snapshot"]["source_sha256"]) == 64
        assert len(body["boards"]) == 2
        by_type = {item["type"]: item for item in body["boards"]}
        assert by_type["TGBT"]["receivers"] == 3
        assert by_type["DIVISIONNAIRE"]["receivers"] == 3
        assert len(body["feeders"]) >= 1
        assert len(body["receivers"]) == 3
        assert body["summary"]["totals"]["p_installed_w"] is not None
        assert body["summary"]["totals"]["p_after_ks_w"] is not None
        assert body["receivers"][0]["s_available"] is True
        assert body["receivers"][0]["i_available"] is True
        assert body["receivers"][0]["s_after_ks_va"] is not None
        assert body["receivers"][0]["current_a"] is not None
        assert body["phases"]["p"]["l1"] is not None
        assert body["coherence"]["status"] in {"PASS", "WARN"}
        assert body["config"]["decimals"] == 2


def test_pdf_xlsx_csv_exports_are_readable(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        create_report_project(api)
        body = preview(api)
        first_receiver = body["receivers"][0]
        snapshot_id = body["snapshot"]["snapshot_id"]
        root = tmp_path / "exports"
        pdf = root / "rapport.pdf"
        xlsx = root / "rapport.xlsx"
        csv_dir = root / "csv"

        pdf_response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "pdf", "path": str(pdf)},
        )
        assert pdf_response.status_code == 200, pdf_response.text
        assert pdf.is_file() and pdf.stat().st_size > 1000
        reader = PdfReader(str(pdf))
        assert len(reader.pages) >= 2
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        assert "Rapport WEB-06 test" in text
        assert "Non exposé" in text
        assert "Bilan détaillé des récepteurs" in text
        assert "S retenue" in text
        assert "I retenue" in text
        assert "1,88" in text
        assert "8,17" in text

        landscape_body = preview(api, orientation="landscape")
        landscape_pdf = root / "rapport-paysage.pdf"
        landscape_response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={
                "snapshot_id": landscape_body["snapshot"]["snapshot_id"],
                "format": "pdf",
                "path": str(landscape_pdf),
            },
        )
        assert landscape_response.status_code == 200, landscape_response.text
        landscape_text = "\n".join(
            page.extract_text() or "" for page in PdfReader(str(landscape_pdf)).pages
        )
        assert "Bilan d" in landscape_text and "des r" in landscape_text
        assert "1,88" in landscape_text
        assert "8,17" in landscape_text

        xlsx_response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "xlsx", "path": str(xlsx)},
        )
        assert xlsx_response.status_code == 200, xlsx_response.text
        assert xlsx.is_file()
        workbook = load_workbook(xlsx, data_only=False)
        assert workbook.sheetnames == [
            "Synthèse",
            "TGBT",
            "Tableaux",
            "Départs",
            "Récepteurs",
            "Phases",
            "Hypothèses",
            "Traçabilité",
        ]
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    assert cell.data_type != "f"
        assert workbook["Récepteurs"].max_row == 4
        assert workbook["Récepteurs"]["A1"].value == "Référence"
        receiver_sheet = workbook["Récepteurs"]
        headers = [cell.value for cell in receiver_sheet[1]]
        s_column = headers.index("S (VA)") + 1
        i_column = headers.index("I (A)") + 1
        assert receiver_sheet.cell(row=2, column=s_column).value == first_receiver["s_after_ks_va"]
        assert receiver_sheet.cell(row=2, column=i_column).value == first_receiver["current_a"]
        workbook.close()

        csv_response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "csv", "path": str(csv_dir)},
        )
        assert csv_response.status_code == 200, csv_response.text
        names = {item.name for item in csv_dir.glob("*.csv")}
        assert names == {
            "synthese.csv",
            "tableaux.csv",
            "departs.csv",
            "recepteurs.csv",
            "phases.csv",
            "tracabilite.csv",
        }
        raw = (csv_dir / "recepteurs.csv").read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf")
        text_csv = raw.decode("utf-8-sig")
        assert ";" in text_csv.splitlines()[0]
        assert "\r\n" in text_csv
        rows = list(csv.reader(io.StringIO(text_csv), delimiter=";"))
        assert rows[0][0] == "Référence"
        csv_headers = rows[0]
        csv_s = csv_headers.index("S (VA)")
        csv_i = csv_headers.index("I (A)")
        assert rows[1][csv_s] == first_receiver["s_after_ks_va"]
        assert rows[1][csv_i] == first_receiver["current_a"]
        assert len(rows) == 4

        tableaux_raw = (csv_dir / "tableaux.csv").read_text(encoding="utf-8-sig")
        tableaux_rows = list(csv.reader(io.StringIO(tableaux_raw), delimiter=";"))
        receivers_column = tableaux_rows[0].index("Récepteurs")
        csv_board_counts = {row[0]: row[receivers_column] for row in tableaux_rows[1:]}
        for board in body["boards"]:
            assert csv_board_counts[board["reference"]] == str(board["receivers"])



def test_web05_natif_receiver_values_and_pdf_layout(tmp_path: Path) -> None:
    sample_src = (
        Path(__file__).resolve().parents[2]
        / "packaging"
        / "sample_projects"
        / "web05-native-qualification.segyrcalc-web.json"
    )
    assert sample_src.is_file()
    root = tmp_path / "projects"
    root.mkdir()
    sample = root / sample_src.name
    shutil.copy2(sample_src, sample)
    store = CommandProjectStore(root=root)
    store.open(sample)
    payload = store._payload()
    by_id = {item["id"]: item for item in payload["loads"]}
    assert by_id["REC-03"]["p_after_ku_w"] == "9000"
    assert by_id["REC-03"]["p_after_ks_w"] == "7200"
    assert by_id["REC-03"]["q_after_ks_var"].startswith("3487.119154")
    assert by_id["REC-03"]["s_after_ks_va"] == "8000"
    assert by_id["REC-03"]["current_a"].startswith("11.547005383")
    assert by_id["REC-04"]["p_after_ks_w"] == "2295"
    assert by_id["REC-04"]["s_after_ks_va"] == "2550"
    assert sum(
        Decimal(item["p_after_ks_w"]) for item in payload["loads"]
    ) == Decimal(payload["totals"]["p_after_ks_w"])

    service = ReportService(root=tmp_path / "exports")
    config = ReportConfig(title="Rapport WEB05-NATIF R6.1", orientation="portrait", decimals=2)
    preview = service.preview(store, config)
    pdf_path = tmp_path / "rapport-WEB05-NATIF.pdf"
    service.export(preview["snapshot"]["snapshot_id"], "pdf", pdf_path, overwrite=True)
    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert len(reader.pages) >= 3
    assert "S retenue" in text
    assert "I retenue" in text
    assert "7 200" in text
    assert "3 487,12" in text
    assert "8,00" in text
    assert "11,55" in text
    assert "9,27" in text
    assert "27,97" in text
    assert "AVERTISSEMENT" in text
    assert "9.274" not in text
    assert "27.970" not in text

    xlsx_path = tmp_path / "rapport-WEB05-NATIF.xlsx"
    service.export(preview["snapshot"]["snapshot_id"], "xlsx", xlsx_path, overwrite=True)
    workbook = load_workbook(xlsx_path, data_only=False)
    sheet = workbook.worksheets[4]
    headers = [cell.value for cell in sheet[1]]
    rows = {
        row[0]: dict(zip(headers, row, strict=False))
        for row in sheet.iter_rows(min_row=2, values_only=True)
    }
    workbook.close()
    assert rows["REC-03"]["P retenue (W)"] == "7200"
    assert rows["REC-03"]["S (VA)"] == "8000"
    assert rows["REC-03"]["I (A)"].startswith("11.547005383")

    csv_dir = tmp_path / "csv"
    service.export(preview["snapshot"]["snapshot_id"], "csv", csv_dir, overwrite=True)
    raw = (csv_dir / "recepteurs.csv").read_text(encoding="utf-8-sig")
    reader_rows = list(csv.reader(io.StringIO(raw), delimiter=";"))
    headers = reader_rows[0]
    csv_by_id = {
        row[0]: dict(zip(headers, row, strict=False))
        for row in reader_rows[1:]
    }
    assert csv_by_id["REC-03"]["P retenue (W)"] == "7200"
    assert csv_by_id["REC-03"]["S (VA)"] == "8000"
    assert csv_by_id["REC-03"]["I (A)"].startswith("11.547005383")

def test_existing_files_require_explicit_overwrite(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        create_report_project(api)
        body = preview(api)
        snapshot_id = body["snapshot"]["snapshot_id"]
        target = tmp_path / "exports" / "existant.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"existing")
        refused = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "pdf", "path": str(target)},
        )
        assert refused.status_code == 409
        accepted = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={
                "snapshot_id": snapshot_id,
                "format": "pdf",
                "path": str(target),
                "overwrite": True,
            },
        )
        assert accepted.status_code == 200, accepted.text
        assert target.stat().st_size > 1000


def test_csv_export_does_not_leave_partial_files(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        create_report_project(api)
        body = preview(api)
        snapshot_id = body["snapshot"]["snapshot_id"]
        target = tmp_path / "exports" / "csv-partiel"
        target.mkdir(parents=True)
        (target / "synthese.csv").write_text("existant", encoding="utf-8")
        response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "csv", "path": str(target)},
        )
        assert response.status_code == 409
        assert [item.name for item in target.glob("*.csv")] == ["synthese.csv"]


def test_export_can_write_to_native_user_destination(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        create_report_project(api)
        body = preview(api)
        snapshot_id = body["snapshot"]["snapshot_id"]
        outside = tmp_path / "Bureau OneDrive" / "Rapport avec espaces é.pdf"
        response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "pdf", "path": str(outside)},
        )
        assert response.status_code == 200, response.text
        assert outside.is_file()
        assert outside.stat().st_size > 1000
        file_info = response.json()["files"][0]
        assert file_info["path"] == str(outside)
        assert file_info["bytes"] == outside.stat().st_size
        assert file_info["sha256"] == hashlib.sha256(outside.read_bytes()).hexdigest().upper()

        xlsx = tmp_path / "Bureau OneDrive" / "Rapport.xlsx"
        xlsx_response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "xlsx", "path": str(xlsx)},
        )
        assert xlsx_response.status_code == 200, xlsx_response.text
        assert xlsx.is_file()
        assert len(load_workbook(xlsx).sheetnames) >= 5
        assert len(PdfReader(str(outside)).pages) >= 1

        existing = tmp_path / "Bureau OneDrive" / "existant.pdf"
        existing.write_bytes(b"existing")
        refused = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "pdf", "path": str(existing)},
        )
        assert refused.status_code == 409
        assert existing.read_bytes() == b"existing"
        accepted = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={
                "snapshot_id": snapshot_id,
                "format": "pdf",
                "path": str(existing),
                "overwrite": True,
            },
        )
        assert accepted.status_code == 200, accepted.text
        assert existing.stat().st_size > 1000

        state_before = api.get("/api/project", headers=AUTH).json()["state"]
        csv_dir = tmp_path / "Bureau OneDrive" / "CSV"
        csv_response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "csv", "path": str(csv_dir)},
        )
        assert csv_response.status_code == 200, csv_response.text
        assert len(list(csv_dir.glob("*.csv"))) == 6
        state_after = api.get("/api/project", headers=AUTH).json()["state"]
        assert state_after["revision"] == state_before["revision"]
        assert state_after["calculation_revision"] == state_before["calculation_revision"]
        assert state_after["stale"] is False

        wrong = tmp_path / "exports" / "rapport.csv"
        wrong_response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "pdf", "path": str(wrong)},
        )
        assert wrong_response.status_code == 415

        relative = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "pdf", "path": "rapport.pdf"},
        )
        assert relative.status_code == 422
        assert relative.json()["code"] == "CHEMIN_ABSOLU_REQUIS"


def test_export_write_failure_is_clear_and_does_not_leave_a_file(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        create_report_project(api)
        body = preview(api)
        snapshot_id = body["snapshot"]["snapshot_id"]
        parent_file = tmp_path / "not-a-directory"
        parent_file.write_bytes(b"not-a-directory")
        target = parent_file / "rapport.pdf"
        response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "pdf", "path": str(target)},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "ECRITURE_IMPOSSIBLE"
        assert not target.exists()

        csv_dir = tmp_path / "outside-csv"
        csv_dir.mkdir()
        (csv_dir / "synthese.csv").mkdir()
        csv_response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "csv", "path": str(csv_dir)},
        )
        assert csv_response.status_code == 422
        assert not any(item.is_file() for item in csv_dir.iterdir())


def test_formula_injection_is_neutralized_in_xlsx_and_csv(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        payload = create_report_project(api)
        load = payload["loads"][0]
        updated = api.put(
            f"/api/project/loads/{load['id']}",
            headers=AUTH,
            json={
                "expected_revision": payload["state"]["revision"],
                "feeder_id": load["feeder_id"],
                "designation": '=HYPERLINK("http://example.invalid","x")',
                "network": load["network"],
                "voltage_v": load["voltage_v"],
                "nominal_power": load["nominal_power"],
                "power_unit": load["power_unit"],
                "quantity": load["quantity"],
                "power_factor": load["power_factor"],
                "ku": load["ku"],
                "phase": load["phase"],
            },
        )
        assert updated.status_code == 200, updated.text
        body = preview(api)
        snapshot_id = body["snapshot"]["snapshot_id"]
        xlsx = tmp_path / "exports" / "injection.xlsx"
        api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "xlsx", "path": str(xlsx)},
        )
        workbook = load_workbook(xlsx)
        designations = [workbook["Récepteurs"].cell(row=row, column=2).value for row in range(2, 5)]
        assert any(isinstance(value, str) and value.startswith("'=") for value in designations)
        workbook.close()
        csv_dir = tmp_path / "exports" / "injection-csv"
        api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "csv", "path": str(csv_dir)},
        )
        content = (csv_dir / "recepteurs.csv").read_text(encoding="utf-8-sig")
        assert "'=HYPERLINK" in content


def test_snapshot_is_stable_when_project_changes(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        payload = create_report_project(api)
        body = preview(api)
        snapshot_id = body["snapshot"]["snapshot_id"]
        load = payload["loads"][0]
        changed = api.put(
            f"/api/project/loads/{load['id']}",
            headers=AUTH,
            json={
                "expected_revision": payload["state"]["revision"],
                "feeder_id": load["feeder_id"],
                "designation": load["designation"],
                "network": load["network"],
                "voltage_v": load["voltage_v"],
                "nominal_power": "9000",
                "power_unit": "W",
                "quantity": load["quantity"],
                "power_factor": load["power_factor"],
                "ku": load["ku"],
                "phase": load["phase"],
            },
        )
        assert changed.status_code == 200, changed.text
        target = tmp_path / "exports" / "snapshot.pdf"
        response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "pdf", "path": str(target)},
        )
        assert response.status_code == 200, response.text
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(target)).pages)
        assert str(body["snapshot"]["revision"]) in text
        assert "9000" not in text


def test_csv_delimiter_is_configurable(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        create_report_project(api)
        body = preview(api, csv_delimiter=",")
        snapshot_id = body["snapshot"]["snapshot_id"]
        target = tmp_path / "exports" / "csv-virgule"
        response = api.post(
            "/api/reports/export",
            headers=AUTH,
            json={"snapshot_id": snapshot_id, "format": "csv", "path": str(target)},
        )
        assert response.status_code == 200, response.text
        text = (target / "recepteurs.csv").read_text(encoding="utf-8-sig")
        assert "," in text.splitlines()[0]
        assert ";" not in text.splitlines()[0]


def test_report_configuration_validation(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        create_report_project(api)
        unknown = api.post(
            "/api/reports/preview",
            headers=AUTH,
            json={"config": report_config(sections=["cover", "inconnue"])},
        )
        assert unknown.status_code == 422
        decimals = api.post(
            "/api/reports/preview",
            headers=AUTH,
            json={"config": report_config(decimals=7)},
        )
        assert decimals.status_code == 422
        delimiter = api.post(
            "/api/reports/preview",
            headers=AUTH,
            json={"config": report_config(csv_delimiter="|")},
        )
        assert delimiter.status_code == 422
        options = api.get("/api/reports/options", headers=AUTH)
        assert options.status_code == 200
        assert "pdf" in options.json()["formats"]
        exports = api.get("/api/reports/exports", headers=AUTH)
        assert exports.status_code == 200
        assert "files" in exports.json()
