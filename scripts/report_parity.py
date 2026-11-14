from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openpyxl import load_workbook  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from backend import engine_adapter  # noqa: E402
from backend.project_commands import CommandProjectStore  # noqa: E402
from backend.report_pdf import _display  # noqa: E402
from backend.reporting import EXPORT_ROOT, ReportConfig, ReportService  # noqa: E402

PROJECT = PROJECT_ROOT / "qualification-projects" / "web06-native-web05-import.segyrcalc-web.json"
OUTPUT = (
    PROJECT_ROOT.parent
    / "evidence"
    / "web-reporting-exports-06"
    / "qualification"
    / "report-parity.json"
)


def main() -> int:
    store = CommandProjectStore()
    store.open(PROJECT)
    payload = store._payload()
    result = store.calculation
    if result is None:
        raise RuntimeError("Résultat moteur absent")
    service = ReportService(root=EXPORT_ROOT / "parity")
    config = ReportConfig(
        title="Parité moteur / exports",
        orientation="portrait",
        decimals=2,
    )
    preview = service.preview(store, config)
    snapshot_id = preview["snapshot"]["snapshot_id"]
    target = EXPORT_ROOT / "parity"
    pdf = service.export(snapshot_id, "pdf", target / "parite.pdf", overwrite=True)
    xlsx = service.export(snapshot_id, "xlsx", target / "parite.xlsx", overwrite=True)
    csv_dir = target / "csv"
    service.export(snapshot_id, "csv", csv_dir, overwrite=True)

    workbook = load_workbook(target / "parite.xlsx", data_only=True)
    summary_sheet = workbook["Synthèse"]
    summary = {
        str(row[0]): str(row[1]) if row[1] is not None else ""
        for row in summary_sheet.iter_rows(min_row=2, values_only=True)
        if row[0]
    }
    receiver_sheet = workbook["Récepteurs"]
    receiver_headers = [cell.value for cell in receiver_sheet[1]]
    receiver_rows = [
        dict(zip(receiver_headers, row, strict=False))
        for row in receiver_sheet.iter_rows(min_row=2, values_only=True)
    ]
    workbook.close()

    raw_csv = (csv_dir / "synthese.csv").read_text(encoding="utf-8-sig")
    csv_summary = {row[0]: row[1] for row in csv.reader(io.StringIO(raw_csv), delimiter=";")}
    raw_receivers = (csv_dir / "recepteurs.csv").read_text(encoding="utf-8-sig")
    csv_receivers = list(csv.reader(io.StringIO(raw_receivers), delimiter=";"))
    pdf_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(str(target / "parite.pdf")).pages
    )

    totals = preview["summary"]["totals"]
    engine_values = {
        "p_installed_w": engine_adapter._text(result.p_installed_total_w),
        "p_after_ku_w": engine_adapter._text(result.p_after_ku_total_w),
        "p_after_ks_w": engine_adapter._text(result.p_after_ks_total_w),
        "q_after_ku_var": engine_adapter._text(result.q_after_ku_total_var),
        "q_after_ks_var": engine_adapter._text(result.q_after_ks_total_var),
        "s_after_ku_va": engine_adapter._text(result.s_after_ku_total_va),
        "s_after_ks_va": engine_adapter._text(result.s_after_ks_total_va),
        "neutral_current_a": engine_adapter._text(result.neutral_current_a),
        "unbalance_percent": engine_adapter._text(result.unbalance_percent),
    }
    labels = {
        "p_installed_w": "Puissance installée",
        "p_after_ku_w": "Puissance après Ku",
        "p_after_ks_w": "Puissance retenue",
        "q_after_ku_var": "Puissance réactive après Ku",
        "q_after_ks_var": "Puissance réactive retenue",
        "s_after_ku_va": "Puissance apparente après Ku",
        "s_after_ks_va": "Puissance apparente retenue",
        "neutral_current_a": "Courant neutre",
        "unbalance_percent": "Déséquilibre",
    }
    checks: dict[str, Any] = {}
    for key, engine_value in engine_values.items():
        payload_value = payload["totals"].get(key)
        snapshot_value = totals.get(key)
        xlsx_value = summary.get(labels[key], "")
        csv_value = csv_summary.get(labels[key], "")
        pdf_value = _display(engine_value, 2)
        checks[key] = {
            "engine": engine_value,
            "payload": payload_value,
            "snapshot": snapshot_value,
            "ui_source": snapshot_value,
            "xlsx": xlsx_value,
            "csv": csv_value,
            "pdf_display": pdf_value,
            "pdf_text_present": pdf_value in pdf_text,
            "exact_payload": engine_value == payload_value == snapshot_value,
            "exact_xlsx": engine_value == xlsx_value,
            "exact_csv": engine_value == csv_value,
        }

    first_receiver = preview["receivers"][0]
    xlsx_receiver = next(
        (row for row in receiver_rows if row.get("Référence") == first_receiver["reference"]),
        {},
    )
    csv_receiver = next(
        (row for row in csv_receivers if row and row[0] == first_receiver["reference"]),
        [],
    )
    receiver_checks = {
        "reference": first_receiver["reference"],
        "p_retained_engine_snapshot": first_receiver["p_after_ks_w"],
        "p_retained_xlsx": xlsx_receiver.get("P retenue (W)"),
        "p_retained_csv": csv_receiver[12] if len(csv_receiver) > 12 else None,
        "s_available": first_receiver["s_available"],
        "s_xlsx": xlsx_receiver.get("S (VA)"),
        "i_xlsx": xlsx_receiver.get("I (A)"),
        "s_csv": csv_receiver[15] if len(csv_receiver) > 15 else None,
        "i_csv": csv_receiver[16] if len(csv_receiver) > 16 else None,
        "pdf_s_non_expose": "Non exposé" in pdf_text,
    }
    receiver_checks["pass"] = (
        receiver_checks["p_retained_engine_snapshot"]
        == receiver_checks["p_retained_xlsx"]
        == receiver_checks["p_retained_csv"]
        and receiver_checks["s_available"] is False
        and receiver_checks["s_xlsx"] == "Non exposé"
        and receiver_checks["i_xlsx"] == "Non exposé"
        and receiver_checks["s_csv"] == "Non exposé"
        and receiver_checks["i_csv"] == "Non exposé"
    )
    phase_checks = {}
    engine_phases = {
        "p": engine_adapter._phase_triplet(result.p_phases),
        "q": engine_adapter._phase_triplet(result.q_phases),
        "s": engine_adapter._phase_triplet(result.s_phases),
        "i": engine_adapter._phase_triplet(result.current_phases),
    }
    for key, values in engine_phases.items():
        phase_checks[key] = {
            "engine": values,
            "snapshot": preview["phases"][key],
            "match": values == preview["phases"][key],
        }
    report = {
        "mission": "SEGYRCALC-WEB-DESKTOP-REPORTING-EXPORTS-06",
        "snapshot_id": snapshot_id,
        "snapshot_sha256": preview["snapshot"]["source_sha256"],
        "project_id": preview["snapshot"]["project_id"],
        "revision": preview["snapshot"]["revision"],
        "calculation_revision": preview["snapshot"]["calculation_revision"],
        "totals": checks,
        "receiver": receiver_checks,
        "phases": phase_checks,
        "pdf": {
            "path": pdf["files"][0]["path"],
            "bytes": pdf["files"][0]["bytes"],
            "pages": len(PdfReader(str(target / "parite.pdf")).pages),
        },
        "xlsx": {"path": xlsx["files"][0]["path"], "bytes": xlsx["files"][0]["bytes"]},
        "csv": {"path": str(csv_dir), "files": len(list(csv_dir.glob("*.csv")))},
        "all_checks_pass": all(
            item["exact_payload"]
            and item["exact_xlsx"]
            and item["exact_csv"]
            and item["pdf_text_present"]
            for item in checks.values()
        )
        and receiver_checks["pass"]
        and all(item["match"] for item in phase_checks.values()),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
