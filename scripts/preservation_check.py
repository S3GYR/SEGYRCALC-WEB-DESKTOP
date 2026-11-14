"""Verify protected repositories and previous evidence after WEB-03 work."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEV_ROOT = PROJECT_ROOT.parent.parent
CALCELECT_ROOT = DEV_ROOT.parent
MAIN_REPO = CALCELECT_ROOT / "segyr-calc"
V14_APP = CALCELECT_ROOT / "RECETTE-V14" / "application" / "SEGYRCALC" / "SEGYRCALC.exe"
V14_INSTALLER = (
    DEV_ROOT / "SEGYRCALC-V1.4-WINDOWS-INSTALLER-01" / "output" / "SEGYRCALC-Setup-1.4.0.exe"
)
V15_ROOT = DEV_ROOT / "SEGYRCALC-V1.5-UI-ERGONOMIE-01"
V15_MANIFEST = V15_ROOT / "06-MANIFESTE_SHA256.txt"
EVIDENCE_ROOT = PROJECT_ROOT.parent / "evidence"
WEB01_EVIDENCE = EVIDENCE_ROOT / "web-redesign-architecture-01"
WEB02_EVIDENCE = EVIDENCE_ROOT / "web-ui-implementation-02"
WEB03_EVIDENCE = EVIDENCE_ROOT / "web-project-management-03"
WEB04_EVIDENCE = EVIDENCE_ROOT / "web-electrical-architecture-04"
WEB05_EVIDENCE = EVIDENCE_ROOT / "web-power-balance-05"
WEB06_EVIDENCE = EVIDENCE_ROOT / "web-reporting-exports-06"
OUTPUT = EVIDENCE_ROOT / "web-windows-packaging-07" / "preservation.json"

EXPECTED_V14_APP = "696951ACD54F1390C956E04451BFDE7B0AAE637F7B6EDFF8FB818D235CBBC2B1"
EXPECTED_V14_INSTALLER = "721301316A26CE42E62BF53073CA52409D43CE06DBEA29BDE5C72D2793147BC7"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(MAIN_REPO), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def evidence_counts(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"exists": 0, "files": 0, "top_level": 0}
    files = [item for item in path.rglob("*") if item.is_file()]
    return {
        "exists": 1,
        "files": len(files),
        "top_level": len([item for item in path.iterdir() if item.is_file()]),
        "captures": len(
            [item for item in files if item.suffix.lower() in {".png", ".jpg", ".jpeg"}]
        ),
    }


def v15_manifest() -> dict[str, object]:
    checked = 0
    mismatched: list[str] = []
    missing: list[str] = []
    for line in V15_MANIFEST.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            continue
        if not all(character in "0123456789ABCDEFabcdef" for character in parts[0]):
            continue
        expected, relative = parts
        candidate = Path(relative)
        path = candidate if candidate.is_absolute() else V15_ROOT / relative.replace("\\", "/")
        checked += 1
        if not path.is_file():
            missing.append(relative)
            continue
        if sha256(path) != expected.upper():
            mismatched.append(relative)
    return {
        "manifest": str(V15_MANIFEST),
        "checked": checked,
        "mismatched": len(mismatched),
        "missing": len(missing),
        "mismatched_files": mismatched,
        "missing_files": missing,
        "pass": checked > 0 and not mismatched and not missing,
    }


def main() -> int:
    head = git("rev-parse", "HEAD")
    status = [line for line in git("status", "--porcelain=v1").splitlines() if line.strip()]
    v14_app_hash = sha256(V14_APP) if V14_APP.is_file() else "MISSING"
    v14_installer_hash = sha256(V14_INSTALLER) if V14_INSTALLER.is_file() else "MISSING"
    v15 = v15_manifest()
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "main_repository": {
            "path": str(MAIN_REPO),
            "head": head,
            "expected_head": "2decbc8a7e31fbb20fd2d18808ebd0f6b76c259c",
            "head_unchanged": head == "2decbc8a7e31fbb20fd2d18808ebd0f6b76c259c",
            "status_count": len(status),
            "status": status,
            "status_count_expected": 10,
            "status_unchanged": len(status) == 10,
        },
        "v14": {
            "application": str(V14_APP),
            "application_sha256": v14_app_hash,
            "application_expected": EXPECTED_V14_APP,
            "application_match": v14_app_hash == EXPECTED_V14_APP,
            "installer": str(V14_INSTALLER),
            "installer_sha256": v14_installer_hash,
            "installer_expected": EXPECTED_V14_INSTALLER,
            "installer_match": v14_installer_hash == EXPECTED_V14_INSTALLER,
        },
        "v15": v15,
        "previous_evidence": {
            "web01": evidence_counts(WEB01_EVIDENCE),
            "web02": evidence_counts(WEB02_EVIDENCE),
            "web03": evidence_counts(WEB03_EVIDENCE),
            "web04": evidence_counts(WEB04_EVIDENCE),
            "web05": evidence_counts(WEB05_EVIDENCE),
            "web06": evidence_counts(WEB06_EVIDENCE),
        },
        "web07": {
            "project_root": str(PROJECT_ROOT),
            "evidence_root": str(EVIDENCE_ROOT / "web-windows-packaging-07"),
        },
    }
    report["all_checks_pass"] = (
        report["main_repository"]["head_unchanged"]
        and report["main_repository"]["status_unchanged"]
        and report["v14"]["application_match"]
        and report["v14"]["installer_match"]
        and report["v15"]["pass"]
        and report["previous_evidence"]["web01"]["files"] > 0
        and report["previous_evidence"]["web02"]["files"] > 0
        and report["previous_evidence"]["web03"]["files"] > 0
        and report["previous_evidence"]["web04"]["files"] > 0
        and report["previous_evidence"]["web05"]["files"] > 0
        and report["previous_evidence"]["web06"]["files"] > 0
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
