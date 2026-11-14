"""Measure the isolated prototype's local API and process baseline."""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import psutil

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.desktop import ServerHandle, _redacted_url  # noqa: E402


def timed_call(client: httpx.Client, method: str, path: str, **kwargs: Any) -> float:
    start = time.perf_counter()
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return (time.perf_counter() - start) * 1000


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "count": float(len(values)),
        "min_ms": round(min(values), 3),
        "median_ms": round(statistics.median(values), 3),
        "mean_ms": round(statistics.mean(values), 3),
        "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 3),
        "max_ms": round(max(values), 3),
    }


def main() -> int:
    output = Path(sys.argv[2]) if len(sys.argv) >= 3 and sys.argv[1] == "--output" else None
    handle = ServerHandle()
    started = time.perf_counter()
    url = handle.start()
    startup_ms = (time.perf_counter() - started) * 1000
    assert handle.port is not None
    headers = {"X-SEGYR-Token": handle.token}
    power_body = {
        "mode": "P_KNOWN",
        "network": "TRI",
        "voltage_v": "400",
        "power_value": "8000",
        "power_unit": "W",
        "power_factor": "0.8",
        "power_nature": "ABSORBED",
        "efficiency": None,
    }
    with httpx.Client(
        base_url=f"http://127.0.0.1:{handle.port}", headers=headers, timeout=20
    ) as client:
        health = [timed_call(client, "GET", "/api/health") for _ in range(10)]
        project = [timed_call(client, "GET", "/api/engine/project") for _ in range(5)]
        power = [
            timed_call(client, "POST", "/api/engine/power", json=power_body) for _ in range(20)
        ]
        project_payload = client.get("/api/engine/project").json()
        power_payload = client.post("/api/engine/power", json=power_body).json()
        process = psutil.Process()
        rss_mb = process.memory_info().rss / (1024 * 1024)
        cpu_percent = process.cpu_percent(interval=0.2)

    close_started = time.perf_counter()
    handle.stop()
    shutdown_ms = (time.perf_counter() - close_started) * 1000

    dist = PROJECT_ROOT / "frontend" / "dist"
    dist_files = [path for path in dist.rglob("*") if path.is_file()]
    dist_bytes = sum(path.stat().st_size for path in dist_files)
    js_bytes = sum(path.stat().st_size for path in dist_files if path.suffix == ".js")
    css_bytes = sum(path.stat().st_size for path in dist_files if path.suffix == ".css")

    report = {
        "mission": "SEGYRCALC-WEB-DESKTOP-UI-IMPLEMENTATION-02",
        "measured_at": datetime.now(UTC).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor": platform.processor(),
            "machine": platform.machine(),
        },
        "server_startup_ms": round(startup_ms, 3),
        "health": summarize(health),
        "project_calculation": summarize(project),
        "power_calculation": summarize(power),
        "process_rss_mb": round(rss_mb, 2),
        "process_cpu_percent_during_measurement": round(cpu_percent, 2),
        "shutdown_ms": round(shutdown_ms, 3),
        "project_result": {
            "status": project_payload["status"],
            "load_count": project_payload["project"]["load_count"],
            "load_rows": len(project_payload["loads"]),
            "p_installed_w": project_payload["totals"]["p_installed_w"],
            "p_after_ks_w": project_payload["totals"]["p_after_ks_w"],
        },
        "power_result": {
            "status": power_payload["status"],
            "current_a": power_payload["current_a"],
        },
        "frontend_dist": {
            "files": len(dist_files),
            "total_bytes": dist_bytes,
            "js_bytes": js_bytes,
            "css_bytes": css_bytes,
        },
        "redacted_local_url": _redacted_url(url),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
