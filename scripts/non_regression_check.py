"""Compare the prototype adapter with direct calls to the qualified engine."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import engine_adapter  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def manifest_value(path: Path) -> str | None:
    root = next(
        (parent for parent in path.parents if (parent / "06-MANIFESTE_SHA256.txt").is_file()),
        None,
    )
    if root is None:
        return None
    manifest = root / "06-MANIFESTE_SHA256.txt"
    relative = path.relative_to(root).as_posix()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].replace("\\", "/") == relative:
            return parts[0].upper()
    return None


def main() -> int:
    from calcelect.service_v11 import calculate_project_v11

    output = Path(sys.argv[2]) if len(sys.argv) >= 3 and sys.argv[1] == "--output" else None
    power_request = {
        "mode": "P_KNOWN",
        "network": "TRI",
        "voltage_v": "400",
        "power_value": "8000",
        "power_unit": "W",
        "power_factor": "0.8",
        "power_nature": "ABSORBED",
        "efficiency": None,
    }
    direct_power = engine_adapter.calculate_power(
        mode="P_KNOWN",
        network="TRI",
        voltage_v="400",
        power_value="8000",
        power_unit="W",
        power_factor="0.8",
    )
    adapter_power = engine_adapter.calculate_power_payload(power_request)

    direct_project = engine_adapter.calculate_project_v13(
        engine_adapter.load_project_v13(engine_adapter.FIXTURE)
    )
    adapter_project = engine_adapter.load_project_payload()

    power_checks = {
        "status": engine_adapter._enum_text(direct_power.status) == adapter_power["status"],
        "p_abs": engine_adapter._text(direct_power.p_abs_w) == adapter_power["p_abs_w"],
        "q": engine_adapter._text(direct_power.q_var) == adapter_power["q_var"],
        "s": engine_adapter._text(direct_power.s_va) == adapter_power["s_va"],
        "current": engine_adapter._text(direct_power.current_a) == adapter_power["current_a"],
    }
    v11_project = engine_adapter.load_project_v13(engine_adapter.FIXTURE)
    v11_result = calculate_project_v11(v11_project)
    direct_totals: dict[str, dict[str, object]] = {}
    for feeder_result in v11_result.feeder_results:
        if feeder_result.ks_result is not None:
            for contribution in feeder_result.ks_result.contributions:
                source = contribution.source
                direct_totals[contribution.load_id] = {
                    "p_after_ku_w": source.p_used_after_w,
                    "q_after_ku_var": source.q_used_after_var,
                    "p_after_ks_w": contribution.p_after_w,
                    "q_after_ks_var": contribution.q_after_var,
                    "s_after_ks_va": contribution.s_after_va,
                    "current_a": contribution.current_after_a,
                }
        elif feeder_result.group_result is not None:
            for contribution in feeder_result.group_result.contributions:
                direct_totals[contribution.load_id] = {
                    "p_after_ku_w": contribution.p_used_after_w,
                    "q_after_ku_var": contribution.q_used_after_var,
                    "p_after_ks_w": contribution.p_used_after_w,
                    "q_after_ks_var": contribution.q_used_after_var,
                    "s_after_ks_va": contribution.s_used_after_va,
                    "current_a": contribution.current_after_a,
                }
    adapter_loads = {load["id"]: load for load in adapter_project["loads"]}
    load_checks = {}
    for load_id, expected_load in direct_totals.items():
        payload = adapter_loads.get(load_id)
        if payload is None:
            load_checks[load_id] = False
            continue
        load_checks[load_id] = all(
            engine_adapter._text(value) == payload[field]  # type: ignore[arg-type]
            for field, value in expected_load.items()
        )

    project_checks = {
        "status": engine_adapter._enum_text(direct_project.status) == adapter_project["status"],
        "load_rows": len(direct_project.project.loads) == len(adapter_project["loads"]),
        "load_contribution_match": all(load_checks.values()) and len(load_checks) > 0,
        "p_installed": engine_adapter._text(direct_project.p_installed_total_w)
        == adapter_project["totals"]["p_installed_w"],
        "p_after_ks": engine_adapter._text(direct_project.p_after_ks_total_w)
        == adapter_project["totals"]["p_after_ks_w"],
        "s_after_ks": engine_adapter._text(direct_project.s_after_ks_total_va)
        == adapter_project["totals"]["s_after_ks_va"],
        "board_count": direct_project.board_count == len(adapter_project["boards"]),
        "feeder_count": direct_project.feeder_count == len(adapter_project["feeders"]),
        "neutral": engine_adapter._text(direct_project.neutral_current_a)
        == adapter_project["totals"]["neutral_current_a"],
        "unbalance": engine_adapter._text(direct_project.unbalance_percent)
        == adapter_project["totals"]["unbalance_percent"],
    }
    deterministic = (
        len(
            {
                json.dumps(engine_adapter.calculate_power_payload(power_request), sort_keys=True)
                for _ in range(20)
            }
        )
        == 1
    )

    engine_files = [
        engine_adapter.POWER_SOURCE,
        engine_adapter.PROJECT_SOURCE,
        engine_adapter.ENGINE_SRC / "calcelect" / "phase_service.py",
        engine_adapter.ENGINE_SRC / "calcelect" / "hierarchy.py",
    ]
    preservation = []
    for path in engine_files:
        actual = sha256(path)
        manifest_sha = manifest_value(path)
        preservation.append(
            {
                "path": str(path),
                "sha256": actual,
                "manifest_sha256": manifest_sha,
                "matches_manifest": manifest_sha is None or actual == manifest_sha,
            }
        )

    report = {
        "mission": "SEGYRCALC-WEB-DESKTOP-REPORTING-EXPORTS-06",
        "power_direct": {
            "status": adapter_power["status"],
            "p_abs_w": adapter_power["p_abs_w"],
            "q_var": adapter_power["q_var"],
            "s_va": adapter_power["s_va"],
            "current_a": adapter_power["current_a"],
        },
        "project_direct": {
            "status": adapter_project["status"],
            "p_installed_w": adapter_project["totals"]["p_installed_w"],
            "p_after_ks_w": adapter_project["totals"]["p_after_ks_w"],
            "s_after_ks_va": adapter_project["totals"]["s_after_ks_va"],
            "neutral_current_a": adapter_project["totals"]["neutral_current_a"],
            "unbalance_percent": adapter_project["totals"]["unbalance_percent"],
        },
        "power_checks": power_checks,
        "project_checks": project_checks,
        "deterministic_20_calls": deterministic,
        "engine_source_preservation": preservation,
        "all_checks_pass": all(power_checks.values())
        and all(project_checks.values())
        and deterministic
        and all(item["matches_manifest"] for item in preservation),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
