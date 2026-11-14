from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.desktop import ServerHandle, _redacted_url  # noqa: E402
from backend.reporting import EXPORT_ROOT  # noqa: E402

PROJECT = PROJECT_ROOT / "qualification-projects" / "web06-native-web05-import.segyrcalc-web.json"
OUTPUT = (
    PROJECT_ROOT.parent
    / "evidence"
    / "web-reporting-exports-06"
    / "qualification"
    / "offline-security.json"
)
CAPTURE = (
    PROJECT_ROOT.parent
    / "evidence"
    / "web-reporting-exports-06"
    / "captures"
    / "14-rapports-offline.png"
)


def main() -> int:
    handle = ServerHandle()
    requests: list[str] = []
    failed: list[str] = []
    result: dict[str, object] = {}
    pdf = EXPORT_ROOT / "offline" / "offline.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.unlink(missing_ok=True)
    try:
        url = handle.start()
        opened = handle.request("POST", "/api/project/open", json={"path": str(PROJECT)})
        if opened.status_code != 200:
            raise RuntimeError(f"Ouverture impossible: {opened.text}")
        root = handle.request("GET", "/")
        openapi = handle.request("GET", "/openapi.json")
        docs = handle.request("GET", "/docs")
        cors = handle.request("GET", "/api/project")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900}, locale="fr-FR")
            page.on("request", lambda request: requests.append(request.url))
            page.on("requestfailed", lambda request: failed.append(request.url))
            page.goto(f"{url}?screen=reports", wait_until="networkidle")
            page.wait_for_timeout(300)
            page.click('[data-testid="report-preview-generate"]')
            page.wait_for_selector('[data-testid="report-preview"]')
            page.click('[data-testid="report-export-pdf"]')
            page.wait_for_selector('[data-testid="export-path-dialog"]')
            page.fill('[data-testid="export-path-input"]', str(pdf))
            page.click('[data-testid="export-confirm"]')
            page.wait_for_selector('[data-testid="report-export-result"]')
            page.wait_for_timeout(300)
            CAPTURE.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(CAPTURE), full_page=False)
            browser.close()
    finally:
        handle.stop()
    parsed = [(item, urlparse(item)) for item in requests]
    external = [item for item, parts in parsed if parts.hostname not in {"127.0.0.1", "localhost"}]
    local = [item for item, parts in parsed if parts.hostname in {"127.0.0.1", "localhost"}]
    artifacts = [pdf]
    if pdf.is_file():
        for path in (pdf.parent / "csv").glob("*.csv"):
            artifacts.append(path)
        xlsx = pdf.parent / "offline.xlsx"
        if xlsx.is_file():
            artifacts.append(xlsx)
    token_leaks = []
    for path in artifacts:
        if path.is_file() and handle.token.encode("utf-8") in path.read_bytes():
            token_leaks.append(str(path))
    result = {
        "mission": "SEGYRCALC-WEB-DESKTOP-REPORTING-EXPORTS-06",
        "url": _redacted_url(url),
        "local_requests": len(local),
        "external_requests": len(external),
        "external_urls": external,
        "failed_requests": failed,
        "request_samples": local[:10],
        "header_csp": "Content-Security-Policy" in root.headers,
        "header_cors": "Access-Control-Allow-Origin" in root.headers,
        "cors_probe_status": cors.status_code,
        "openapi_status": openapi.status_code,
        "docs_status": docs.status_code,
        "pdf_exists": pdf.is_file(),
        "pdf_bytes": pdf.stat().st_size if pdf.is_file() else 0,
        "token_leak_files": token_leaks,
        "capture": str(CAPTURE),
        "all_checks_pass": (
            not external
            and len(local) > 0
            and "Content-Security-Policy" in root.headers
            and "Access-Control-Allow-Origin" not in root.headers
            and openapi.status_code == 404
            and docs.status_code == 404
            and pdf.is_file()
            and not token_leaks
        ),
        "limitations": [
            "Contrôle hors ligne sur Chromium headless, pas WebView2 natif.",
            "Loopback + jeton n'est pas une authentification forte.",
            "Le contrôle ne remplace pas un audit réseau du poste Windows.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
