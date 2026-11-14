from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.desktop import ServerHandle  # noqa: E402


def main() -> int:
    handle = ServerHandle()
    try:
        url = handle.start()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1360, "height": 860}, locale="fr-FR")
            page.goto(f"{url}?screen=projects", wait_until="networkidle")
            page.wait_for_timeout(500)
            result = page.evaluate(
                """() => {
                  const width = window.innerWidth;
                  const offenders = [];
                  for (const element of document.querySelectorAll('body *')) {
                    const rect = element.getBoundingClientRect();
                    if (rect.right > width + 1 || rect.left < -1) {
                      offenders.push({
                        tag: element.tagName,
                        cls: element.className,
                        testid: element.getAttribute('data-testid'),
                        left: Math.round(rect.left),
                        right: Math.round(rect.right),
                        width: Math.round(rect.width),
                        text: (element.textContent || '').slice(0, 80)
                      });
                    }
                  }
                  return {
                    innerWidth: width,
                    scrollWidth: document.documentElement.scrollWidth,
                    offenders: offenders.slice(0, 25)
                  };
                }"""
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            browser.close()
    finally:
        handle.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
