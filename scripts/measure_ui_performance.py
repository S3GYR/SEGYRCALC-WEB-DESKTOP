"""Measure the WEB-02 React UI at 15/100/500/1000 synthetic rows."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.desktop import ServerHandle, _redacted_url  # noqa: E402

CAPTURES = PROJECT_ROOT.parent / "evidence" / "web-ui-implementation-02" / "captures"


def read_metrics(page) -> dict[str, object]:
    cards = page.locator(".summary-card").all_inner_texts()
    chips = page.locator(".metric-chip").all_inner_texts()
    return {
        "summary_cards": cards,
        "metric_chips": chips,
        "dom_rows": page.locator('[data-testid="performance-table"] tbody tr').count(),
        "virtual_note": page.locator(".virtual-note").inner_text()
        if page.locator(".virtual-note").count()
        else None,
    }


def main() -> int:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    output = Path(sys.argv[2]) if len(sys.argv) >= 3 and sys.argv[1] == "--output" else None
    handle = ServerHandle()
    result: dict[str, object] = {}
    try:
        url = handle.start()
        started = time.perf_counter()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 768}, locale="fr-FR")
            page.goto(f"{url}?screen=performance", wait_until="networkidle")
            page.locator('[data-testid="performance-screen"]').wait_for(timeout=10000)
            page.wait_for_timeout(300)
            volumes: dict[str, object] = {}
            for count in ("15", "100", "500", "1000"):
                page.click(f'[data-testid="perf-count-{count}"]')
                page.wait_for_timeout(250)
                volumes[count] = read_metrics(page)
                page.screenshot(
                    path=str(CAPTURES / f"web02-performance-{count}.png"), full_page=True
                )

            page.fill('[data-testid="perf-search"]', "perf 100")
            page.wait_for_timeout(250)
            search_state = read_metrics(page)
            page.fill('[data-testid="perf-search"]', "")
            page.click('[data-testid="perf-sort"]')
            page.wait_for_timeout(250)
            sort_state = read_metrics(page)
            page.select_option('[data-testid="perf-network"]', "TRI")
            page.wait_for_timeout(250)
            filter_state = read_metrics(page)

            for width, height, name in (
                (1366, 768, "1366"),
                (1600, 900, "1600"),
                (1920, 1080, "1920"),
            ):
                page.set_viewport_size({"width": width, "height": height})
                page.goto(f"{url}?screen=balance", wait_until="networkidle")
                page.locator('[data-testid="power-balance-screen"]').wait_for(timeout=10000)
                page.wait_for_timeout(300)
                page.screenshot(path=str(CAPTURES / f"web02-balance-{name}.png"), full_page=False)

            page.set_viewport_size({"width": 1366, "height": 768})
            for screen, name in (
                ("dashboard", "web02-dashboard-1366.png"),
                ("projects", "web02-projects-1366.png"),
                ("architecture", "web02-architecture-1366.png"),
                ("library", "web02-library-1366.png"),
                ("reports", "web02-reports-1366.png"),
                ("settings", "web02-settings-1366.png"),
                ("engine", "web02-engine-1366.png"),
            ):
                page.goto(f"{url}?screen={screen}", wait_until="networkidle")
                page.wait_for_timeout(250)
                page.screenshot(path=str(CAPTURES / name), full_page=False)

            result = {
                "mission": "SEGYRCALC-WEB-DESKTOP-UI-IMPLEMENTATION-02",
                "method": "Playwright 1.65.1, Chrome channel, headless, 1366x768 unless stated",
                "url": _redacted_url(url),
                "volumes": volumes,
                "search": search_state,
                "sort": sort_state,
                "filter": filter_state,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "captures": sorted(path.name for path in CAPTURES.glob("web02-*.png")),
                "limitations": [
                    "Les lignes sont synthétiques et ne sont pas des résultats du moteur.",
                    "Les métriques sont des mesures d'affichage React, pas une capacité du moteur.",
                    "WebView2 natif est mesuré séparément par les scénarios pywebview.",
                ],
            }
            browser.close()
    finally:
        handle.stop()
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
