"""Run an axe-core WCAG A/AA scan against the local WEB-03 interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.desktop import ServerHandle  # noqa: E402

AXE = PROJECT_ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"


def main() -> int:
    output = Path(sys.argv[2]) if len(sys.argv) >= 3 and sys.argv[1] == "--output" else None
    handle = ServerHandle()
    report: dict[str, object] = {}
    try:
        url = handle.start()
        created = handle.request(
            "POST",
            "/api/project/new",
            json={
                "name": "Projet accessibilité WEB-03",
                "reference": "A11Y-WEB03",
                "client": "SEGYR Technologies",
                "site": "Site accessibilité",
                "address": "4 rue de l'Accessibilité",
                "author": "Qualification",
                "description": "Projet de contrôle axe-core",
                "observations": "Contrôle automatique uniquement",
                "revision": "A",
                "standard": "NF C 15-100",
                "network": "TRI",
                "voltage_v": "400",
                "has_neutral": True,
                "voltage_ln_v": "230",
            },
        )
        if created.status_code != 200:
            raise RuntimeError(f"Création du projet d'accessibilité impossible: {created.text}")
        state = created.json()
        board = handle.request(
            "POST",
            "/api/project/boards",
            json={
                "expected_revision": state["state"]["revision"],
                "parent_board_id": "TGBT-01",
                "designation": "Tableau accessibilité",
                "has_neutral": True,
                "voltage_ln_v": "230",
            },
        )
        board_state = board.json()
        divisionnaire = next(
            item for item in board_state["boards"] if item["type"] == "DIVISIONNAIRE"
        )
        feeder = handle.request(
            "POST",
            "/api/project/feeders",
            json={
                "expected_revision": board_state["state"]["revision"],
                "parent_board_id": divisionnaire["id"],
                "designation": "Départ accessibilité",
                "ks": "0.9",
                "has_neutral": True,
            },
        )
        feeder_state = feeder.json()
        terminal = next(
            item
            for item in feeder_state["feeders"]
            if item["designation"] == "Départ accessibilité"
        )
        handle.request(
            "POST",
            "/api/project/loads",
            json={
                "expected_revision": feeder_state["state"]["revision"],
                "feeder_id": terminal["id"],
                "designation": "Récepteur accessibilité",
                "network": "TRI",
                "voltage_v": "400",
                "nominal_power": "3000",
                "power_unit": "W",
                "quantity": 1,
                "power_factor": "0.9",
                "ku": "0.8",
                "phase": None,
            },
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900}, locale="fr-FR")
            screens: dict[str, dict[str, Any]] = {}
            for screen in (
                "dashboard",
                "projects",
                "architecture",
                "balance",
                "reports",
                "settings",
                "engine",
            ):
                page.goto(f"{url}?screen={screen}", wait_until="networkidle")
                page.wait_for_timeout(300)
                # CSP blocks inline script tags; evaluate the local axe bundle through CDP.
                page.evaluate(AXE.read_text(encoding="utf-8"))
                result = cast(
                    dict[str, Any],
                    page.evaluate(
                        """async () => await axe.run(document, {
                          runOnly: { type: 'tag',
                            values: ['wcag2a','wcag2aa','wcag21a','wcag21aa'] }
                        })"""
                    ),
                )
                screens[screen] = {
                    "violations": [
                        {
                            "id": item["id"],
                            "impact": item["impact"],
                            "help": item["help"],
                            "nodes": [node["target"] for node in item["nodes"]],
                        }
                        for item in result["violations"]
                    ],
                    "passes": len(result["passes"]),
                    "incomplete": len(result["incomplete"]),
                }
            dialogs: dict[str, dict[str, Any]] = {}
            dialog_case = (
                (
                    "project-create-dialog",
                    "projects",
                    '[data-testid="project-new"]',
                    '[data-testid="project-form-dialog"]',
                ),
                (
                    "architecture-add-dialog",
                    "architecture",
                    '[data-testid="add-board"]',
                    '[data-testid="entity-dialog"]',
                ),
                (
                    "save-as-dialog",
                    "projects",
                    '[data-testid="project-save"]',
                    '[data-testid="path-dialog"]',
                ),
            )
            for label, screen, trigger, selector in dialog_case:
                page.goto(f"{url}?screen={screen}", wait_until="networkidle")
                page.wait_for_timeout(300)
                page.click(trigger)
                page.wait_for_selector(selector)
                page.evaluate(AXE.read_text(encoding="utf-8"))
                result = cast(
                    dict[str, Any],
                    page.evaluate(
                        """async () => await axe.run(document, {
                          runOnly: { type: 'tag',
                            values: ['wcag2a','wcag2aa','wcag21a','wcag21aa'] }
                        })"""
                    ),
                )
                dialogs[label] = {
                    "violations": [
                        {
                            "id": item["id"],
                            "impact": item["impact"],
                            "help": item["help"],
                            "nodes": [node["target"] for node in item["nodes"]],
                        }
                        for item in result["violations"]
                    ],
                    "passes": len(result["passes"]),
                    "incomplete": len(result["incomplete"]),
                }
            page.goto(f"{url}?screen=reports", wait_until="networkidle")
            page.wait_for_timeout(300)
            page.click('[data-testid="report-preview-generate"]')
            page.wait_for_selector('[data-testid="report-preview"]')
            page.click('[data-testid="report-export-pdf"]')
            page.wait_for_selector('[data-testid="export-path-dialog"]')
            page.evaluate(AXE.read_text(encoding="utf-8"))
            result = cast(
                dict[str, Any],
                page.evaluate(
                    """async () => await axe.run(document, {
                      runOnly: { type: 'tag',
                        values: ['wcag2a','wcag2aa','wcag21a','wcag21aa'] }
                    })"""
                ),
            )
            dialogs["report-export-dialog"] = {
                "violations": [
                    {
                        "id": item["id"],
                        "impact": item["impact"],
                        "help": item["help"],
                        "nodes": [node["target"] for node in item["nodes"]],
                    }
                    for item in result["violations"]
                ],
                "passes": len(result["passes"]),
                "incomplete": len(result["incomplete"]),
            }
            report = {
                "tool": "axe-core 4.10.2",
                "standard": "WCAG 2.0/2.1 A/AA (automatic checks)",
                "screens": screens,
                "dialogs": dialogs,
                "violation_count": sum(len(value["violations"]) for value in screens.values())
                + sum(len(value["violations"]) for value in dialogs.values()),
                "limitations": [
                    "Les contrôles automatiques ne remplacent pas un audit manuel.",
                    "Les tableaux denses, le clavier et les lecteurs d'écran restent "
                    "à qualifier manuellement.",
                    "Le scan porte sur Chromium headless, pas sur WebView2 natif.",
                ],
            }
            browser.close()
    finally:
        handle.stop()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report.get("violation_count", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
