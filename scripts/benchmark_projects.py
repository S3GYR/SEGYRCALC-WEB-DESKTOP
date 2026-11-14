"""Measure isolated WEB-03 project creation, save, open and recalculation.

The datasets are synthetic and live only in qualification-projects/perf.
No electrical formula is duplicated here: every result comes from the engine.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGINE_SRC = PROJECT_ROOT.parent.parent / "SEGYRCALC-V1.5-UI-ERGONOMIE-01" / "worktree" / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(ENGINE_SRC))

from calcelect.hierarchy import Board, BoardType, Feeder, LoadAssignment, ProjectV11  # noqa: E402
from calcelect.models import LoadEntry  # noqa: E402
from calcelect.project_v14 import ProjectMetadataV14, ProjectV14  # noqa: E402
from segyr_calc.a2.models import Load  # noqa: E402

from backend import engine_adapter  # noqa: E402
from backend.project_store import ProjectStore, WebMetadata  # noqa: E402

COUNT_SIZES = (15, 100, 500, 1000)
EVIDENCE = PROJECT_ROOT.parent / "evidence" / "web-power-balance-05"
PERF_ROOT = PROJECT_ROOT / "qualification-projects" / "perf"


def build_project(count: int) -> ProjectV14:
    project = ProjectV11.new(
        name=f"Performance {count} récepteurs",
        reference=f"PERF-{count:04d}",
        client="Jeu fictif de performance",
        description="Projet synthétique de mesure, aucune donnée propriétaire.",
    )
    project = project.add_board(
        Board(
            board_id="TGBT-01",
            designation="TGBT performance",
            board_type=BoardType.TGBT,
            network="TRI",
            voltage_v="400",
            has_neutral=True,
            voltage_ln_v="230",
        )
    )
    project = project.add_board_with_feeder(
        Board(
            board_id="TD-01",
            designation="Tableau performance",
            board_type=BoardType.DIVISIONNAIRE,
            network="TRI",
            voltage_v="400",
            parent_feeder_id="DEP-01",
            has_neutral=True,
            voltage_ln_v="230",
        ),
        Feeder(
            feeder_id="DEP-01",
            designation="Alimentation tableau performance",
            parent_board_id="TGBT-01",
            network="TRI",
            voltage_v="400",
            downstream_board_id="TD-01",
            has_neutral=True,
        ),
    )
    project = project.add_feeder(
        Feeder(
            feeder_id="DEP-02",
            designation="Départ performance",
            parent_board_id="TD-01",
            network="TRI",
            voltage_v="400",
            ks="0.9",
            has_neutral=True,
            draft=True,
        )
    )
    for index in range(count):
        load = Load(
            load_id=f"REC-{index + 1:04d}",
            designation=f"Récepteur fictif {index + 1}",
            network="TRI",
            voltage_v="400",
            nominal_power=str(1000 + (index % 7) * 100),
            power_unit="W",
            quantity=1,
            power_factor="0.9",
        )
        project = project.add_load(
            LoadAssignment(
                entry=LoadEntry(load=load, ku=str(0.5 + (index % 5) / 10)),
                feeder_id="DEP-02",
                phase=None,
            )
        )
    metadata = ProjectMetadataV14.new(
        code=f"PERF-{count:04d}",
        designation=f"Performance {count} récepteurs",
        author="Qualification WEB-03",
        revision="A",
        standard="NF C 15-100",
    )
    return ProjectV14(electrical=project, metadata=metadata)


def measure(count: int) -> dict[str, object]:
    process = psutil.Process()
    rss_before = process.memory_info().rss / (1024 * 1024)
    started = time.perf_counter()
    built = build_project(count)
    creation_ms = (time.perf_counter() - started) * 1000

    store = ProjectStore(root=PERF_ROOT)
    store.project = built
    store.web = WebMetadata(
        site="Site fictif de performance",
        observations="Projet synthétique de mesure.",
        created_by="Qualification WEB-03",
    )
    store.revision = 1
    started = time.perf_counter()
    store._recalculate()
    initial_calc_ms = (time.perf_counter() - started) * 1000

    target = PERF_ROOT / f"perf-{count:04d}.segyrcalc-web.json"
    target.unlink(missing_ok=True)
    target.with_name(target.name + ".bak").unlink(missing_ok=True)
    started = time.perf_counter()
    store.save(target, overwrite=False)
    save_ms = (time.perf_counter() - started) * 1000

    reader = ProjectStore(root=PERF_ROOT)
    started = time.perf_counter()
    reader.open(target)
    open_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    reader.recalculate()
    recalc_ms = (time.perf_counter() - started) * 1000

    rss_after = process.memory_info().rss / (1024 * 1024)
    started = time.perf_counter()
    reader.close()
    close_ms = (time.perf_counter() - started) * 1000

    return {
        "receiver_count": count,
        "creation_ms": round(creation_ms, 3),
        "initial_calculation_ms": round(initial_calc_ms, 3),
        "save_ms": round(save_ms, 3),
        "open_ms": round(open_ms, 3),
        "recalculation_ms": round(recalc_ms, 3),
        "close_ms": round(close_ms, 3),
        "file_bytes": target.stat().st_size,
        "rss_before_mb": round(rss_before, 2),
        "rss_after_mb": round(rss_after, 2),
        "rss_delta_mb": round(rss_after - rss_before, 2),
        "file": str(target),
    }


def main() -> int:
    PERF_ROOT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = [measure(count) for count in COUNT_SIZES]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "data_class": "SYNTHETIC_PERFORMANCE_FIXTURES",
        "engine_source_sha256": engine_adapter.PROJECT_SOURCE_SHA256,
        "environment": {
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "process_rss_mb": round(psutil.Process().memory_info().rss / (1024 * 1024), 2),
        },
        "results": results,
    }
    output = EVIDENCE / "performance-results.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
