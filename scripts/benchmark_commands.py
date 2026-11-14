"""Measure WEB-04 transactional commands on synthetic project sizes."""

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

from backend.project_commands import CommandProjectStore  # noqa: E402
from backend.project_store import WebMetadata  # noqa: E402
from scripts.benchmark_projects import build_project  # noqa: E402

SIZES = (15, 100, 500, 1000)
EVIDENCE = PROJECT_ROOT.parent / "evidence" / "web-power-balance-05"
PERF_ROOT = PROJECT_ROOT / "qualification-projects" / "perf"


def timed(operation):
    started = time.perf_counter()
    result = operation()
    return round((time.perf_counter() - started) * 1000, 3), result


def measure(count: int) -> dict[str, object]:
    process = psutil.Process()
    rss_before = process.memory_info().rss / (1024 * 1024)
    creation_ms, built = timed(lambda: build_project(count))

    store = CommandProjectStore(root=PERF_ROOT)
    store.project = built
    store.web = WebMetadata(
        site="Site fictif WEB-04",
        observations="Mesure de commandes transactionnelles.",
        created_by="Qualification WEB-04",
    )
    store.revision = 1
    store.saved_fingerprint = None
    store._reset_history("Projet de performance")
    store._recalculate()

    feeder_id = "DEP-02"
    board_id = "TD-01"
    add_feeder_ms, feeder_payload = timed(
        lambda: store.add_feeder(
            {
                "expected_revision": store.revision,
                "parent_board_id": board_id,
                "designation": "Départ destination performance",
                "ks": "0.9",
                "has_neutral": True,
            }
        )
    )
    destination = max(feeder_payload["feeders"], key=lambda item: item["id"])["id"]

    add_load_ms, added = timed(
        lambda: store.add_load(
            {
                "expected_revision": store.revision,
                "feeder_id": feeder_id,
                "designation": "Récepteur performance commande",
                "network": "TRI",
                "voltage_v": "400",
                "nominal_power": "5000",
                "power_unit": "W",
                "quantity": 2,
                "power_factor": "0.9",
                "ku": "0.5",
                "phase": None,
            }
        )
    )
    load_id = max(added["loads"], key=lambda item: item["id"])["id"]
    update_ms, updated = timed(
        lambda: store.update_load(
            {
                "expected_revision": store.revision,
                "load_id": load_id,
                "feeder_id": feeder_id,
                "designation": "Récepteur performance modifié",
                "network": "TRI",
                "voltage_v": "400",
                "nominal_power": "7000",
                "power_unit": "W",
                "quantity": 2,
                "power_factor": "0.9",
                "ku": "0.5",
                "phase": None,
            }
        )
    )
    before_ids = {item["id"] for item in updated["loads"]}
    duplicate_ms, duplicated = timed(
        lambda: store.duplicate_load(
            {
                "expected_revision": store.revision,
                "load_id": load_id,
                "destination_feeder_id": destination,
            }
        )
    )
    copy_id = next(item["id"] for item in duplicated["loads"] if item["id"] not in before_ids)
    move_ms, _ = timed(
        lambda: store.move_load(
            {
                "expected_revision": store.revision,
                "load_id": copy_id,
                "destination_feeder_id": feeder_id,
            }
        )
    )
    delete_ms, _ = timed(
        lambda: store.delete(
            "load",
            copy_id,
            cascade=False,
            expected_revision=store.revision,
        )
    )
    undo_ms, _ = timed(lambda: store.undo(store.revision))
    redo_ms, _ = timed(lambda: store.redo(store.revision))
    recalc_ms, _ = timed(store.recalculate)
    target = PERF_ROOT / f"commands-{count:04d}.segyrcalc-web.json"
    target.unlink(missing_ok=True)
    save_ms, _ = timed(lambda: store.save(target, overwrite=False))
    reader = CommandProjectStore(root=PERF_ROOT)
    open_ms, _ = timed(lambda: reader.open(target))
    rss_after = process.memory_info().rss / (1024 * 1024)

    return {
        "receivers": count,
        "creation_ms": creation_ms,
        "add_feeder_ms": add_feeder_ms,
        "add_receiver_ms": add_load_ms,
        "update_receiver_ms": update_ms,
        "duplicate_receiver_ms": duplicate_ms,
        "move_receiver_ms": move_ms,
        "delete_receiver_ms": delete_ms,
        "undo_ms": undo_ms,
        "redo_ms": redo_ms,
        "recalculation_ms": recalc_ms,
        "save_ms": save_ms,
        "open_ms": open_ms,
        "file_bytes": target.stat().st_size,
        "rss_delta_mb": round(rss_after - rss_before, 2),
        "history_length": store.state["history_length"],
    }


def main() -> int:
    PERF_ROOT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = [measure(size) for size in SIZES]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "data_class": "SYNTHETIC_WEB05_BALANCE_PERFORMANCE",
        "results": results,
    }
    output = EVIDENCE / "performance-commands.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
