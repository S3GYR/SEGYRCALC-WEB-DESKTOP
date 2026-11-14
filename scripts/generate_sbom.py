from __future__ import annotations

import json
import subprocess
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "evidence" / "web-windows-packaging-07" / "sbom"
OUT.mkdir(parents=True, exist_ok=True)


def python_sbom() -> None:
    packages = []
    for dist in sorted(
        metadata.distributions(), key=lambda item: (item.metadata.get("Name") or "").lower()
    ):
        name = dist.metadata.get("Name")
        if not name:
            continue
        packages.append(
            {
                "name": name,
                "version": dist.version,
                "license": dist.metadata.get("License") or "NOASSERTION",
                "homepage": dist.metadata.get("Home-page") or "NOASSERTION",
                "summary": dist.metadata.get("Summary") or "",
            }
        )
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": "urn:uuid:segyrcalc-web07-python",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "SEGYRCALC WEB-07",
                "version": "0.7.0",
            }
        },
        "components": [
            {
                "type": "library",
                "name": package["name"],
                "version": package["version"],
                "licenses": [{"license": {"name": package["license"]}}],
                "externalReferences": [{"type": "website", "url": package["homepage"]}],
            }
            for package in packages
        ],
        "limitations": (
            "Licences issues des métadonnées Python locales ; audit juridique non réalisé."
        ),
    }
    (OUT / "sbom-python.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def npm_sbom() -> None:
    result = subprocess.run(
        [__import__("shutil").which("npm.cmd") or "npm", "ls", "--json", "--all"],
        cwd=ROOT / "frontend",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    try:
        tree = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        tree = {}
    packages = {}

    def walk(node: dict) -> None:
        for name, value in (node.get("dependencies") or {}).items():
            if not isinstance(value, dict):
                continue
            packages[name] = value.get("version") or "UNKNOWN"
            walk(value)

    walk(tree)
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": "urn:uuid:segyrcalc-web07-npm",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "name": "SEGYRCALC WEB-07 UI", "version": "0.7.0"}
        },
        "components": [
            {"type": "library", "name": name, "version": version}
            for name, version in sorted(packages.items())
        ],
        "limitations": "SBOM npm issue de npm ls ; licences à confirmer avant distribution.",
    }
    (OUT / "sbom-npm.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    python_sbom()
    npm_sbom()
    print(OUT)
