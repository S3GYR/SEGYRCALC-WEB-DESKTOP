# ruff: noqa: E501
from __future__ import annotations

import csv
import io
import json
import shutil
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import psutil
from openpyxl import load_workbook
from pypdf import PdfReader

from backend.project_commands import (
    CommandProjectStore,
    Load,
    LoadAssignment,
    LoadEntry,
)
from backend.reporting import EXPORT_ROOT, ReportConfig, ReportService

ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT.parent
    / "evidence"
    / "web-reporting-exports-06"
    / "qualification"
    / "performance-results.json"
)


def build_store(count: int, base: Path) -> tuple[CommandProjectStore, dict[str, float]]:
    store = CommandProjectStore(root=base)
    store.new(
        name=f"Performance WEB-06 {count} récepteurs",
        reference=f"WEB06-PERF-{count}",
        client="SEGYR Technologies",
        site="Site de performance",
        address="6 rue du Rapport",
        author="Qualification",
        description="Projet de mesure des exports",
        observations="",
        revision="A",
        standard="NF C 15-100",
        network="TRI",
        voltage_v="400",
        has_neutral=True,
        voltage_ln_v="230",
    )
    payload = store._payload()
    board = payload["boards"][0]
    feeder_payload = store.add_feeder(
        {
            "expected_revision": payload["state"]["revision"],
            "parent_board_id": board["id"],
            "designation": "Départ performance",
            "description": "",
            "ks": "0.9",
            "phase": None,
            "has_neutral": True,
            "voltage_ln_v": "230",
        }
    )
    feeder_id = next(
        item["id"] for item in feeder_payload["feeders"] if not item.get("downstream_board_id")
    )
    started = time.perf_counter()
    assert store.project is not None
    electrical = store.project.electrical
    phases = ("L1", "L2", "L3")
    for index in range(count):
        load = Load(
            load_id=f"REC-{index + 1:05d}",
            designation=f"Récepteur de performance numéro {index + 1} — désignation longue contrôlée",
            network="MONO",
            voltage_v="230",
            nominal_power="1200",
            power_unit="W",
            quantity=1,
            power_factor="0.92",
        )
        electrical = electrical.add_load(
            LoadAssignment(
                entry=LoadEntry(load=load, ku="0.8"),
                feeder_id=feeder_id,
                phase=phases[index % 3],
            )
        )
    build_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    store._commit_candidate(
        "Projet de performance",
        store._payload()["state"]["revision"],
        replace(store.project, electrical=electrical),
    )
    calculation_ms = (time.perf_counter() - started) * 1000
    return store, {"build_ms": round(build_ms, 3), "calculation_ms": round(calculation_ms, 3)}


def measure(count: int) -> dict[str, object]:
    base = ROOT / "qualification-performance" / f"projet-{count}"
    if base.is_dir():
        shutil.rmtree(base)
    export_dir = EXPORT_ROOT / "performance" / f"projet-{count}"
    if export_dir.is_dir():
        shutil.rmtree(export_dir)
    process = psutil.Process()
    started = time.perf_counter()
    store, build = build_store(count, base)
    total_build_ms = (time.perf_counter() - started) * 1000
    rss_before = process.memory_info().rss
    service = ReportService(root=EXPORT_ROOT)
    config = ReportConfig(
        title=f"Bilan de performance — {count} récepteurs",
        orientation="landscape",
        decimals=2,
    )
    started = time.perf_counter()
    preview = service.preview(store, config)
    snapshot_ms = (time.perf_counter() - started) * 1000
    snapshot_id = preview["snapshot"]["snapshot_id"]
    rss_after_snapshot = process.memory_info().rss
    results: dict[str, Any] = {
        "receivers": count,
        "build_ms": round(total_build_ms, 3),
        "electrical_build_ms": build["build_ms"],
        "engine_calculation_ms": build["calculation_ms"],
        "snapshot_ms": round(snapshot_ms, 3),
        "snapshot_rows": len(preview["receivers"]),
        "snapshot_sha256": preview["snapshot"]["source_sha256"],
        "rss_before_mb": round(rss_before / 1024 / 1024, 2),
        "rss_after_snapshot_mb": round(rss_after_snapshot / 1024 / 1024, 2),
        "rss_snapshot_delta_mb": round((rss_after_snapshot - rss_before) / 1024 / 1024, 2),
        "coherence": preview["coherence"]["status"],
    }
    started = time.perf_counter()
    pdf = service.export(snapshot_id, "pdf", export_dir / "rapport.pdf")
    results["pdf_ms"] = round((time.perf_counter() - started) * 1000, 3)
    results["pdf_bytes"] = pdf["files"][0]["bytes"]
    reader = PdfReader(str(export_dir / "rapport.pdf"))
    results["pdf_pages"] = len(reader.pages)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    results["pdf_has_project"] = f"WEB06-PERF-{count}" in text
    results["pdf_has_last_receiver"] = f"REC-{count:05d}" in text
    started = time.perf_counter()
    xlsx = service.export(snapshot_id, "xlsx", export_dir / "rapport.xlsx")
    results["xlsx_ms"] = round((time.perf_counter() - started) * 1000, 3)
    results["xlsx_bytes"] = xlsx["files"][0]["bytes"]
    workbook = load_workbook(export_dir / "rapport.xlsx", data_only=False)
    results["xlsx_sheets"] = workbook.sheetnames
    results["xlsx_receiver_rows"] = workbook["Récepteurs"].max_row
    results["xlsx_formula_cells"] = sum(
        1
        for sheet in workbook.worksheets
        for row in sheet.iter_rows()
        for cell in row
        if cell.data_type == "f"
    )
    workbook.close()
    started = time.perf_counter()
    csv_result = service.export(snapshot_id, "csv", export_dir / "csv")
    results["csv_ms"] = round((time.perf_counter() - started) * 1000, 3)
    results["csv_files"] = [Path(item["path"]).name for item in csv_result["files"]]
    results["csv_bytes"] = sum(item["bytes"] for item in csv_result["files"])
    raw = (export_dir / "csv" / "recepteurs.csv").read_bytes()
    results["csv_bom"] = raw.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))
    results["csv_receiver_rows"] = len(rows) - 1
    results["total_export_ms"] = round(
        results["pdf_ms"] + results["xlsx_ms"] + results["csv_ms"], 3
    )
    results["coherence_after_export"] = service.get_snapshot(snapshot_id).payload["coherence"][
        "status"
    ]
    results["verdict"] = (
        "PASS"
        if results["pdf_pages"] > 1
        and results["pdf_has_project"]
        and results["xlsx_receiver_rows"] == count + 1
        and results["csv_receiver_rows"] == count
        else "FAIL"
    )
    return results


def main() -> int:
    runs: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runs": runs,
    }
    for count in (15, 100, 500, 1000):
        print(json.dumps({"event": "performance_start", "receivers": count}), flush=True)
        measured = measure(count)
        print(json.dumps({"event": "performance_done", **measured}, ensure_ascii=False), flush=True)
        runs.append(measured)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"event": "performance_written", "path": str(RESULT)}, ensure_ascii=False))
    return 0 if all(run["verdict"] == "PASS" for run in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
