from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROTECTED_UNTRACKED = {
    "backend/backup_service.py",
    "backend/tests/test_backup_service.py",
}
DISTRIBUTION = "Recette Windows 11"


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def read_engine_version(source: Path) -> str:
    text = source.read_text(encoding="utf-8")
    match = re.search(r'^ENGINE_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit(f"ENGINE_VERSION introuvable dans {source}")
    return match.group(1)


def source_state(root: Path) -> tuple[str, list[str]]:
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    lines = [line for line in status.splitlines() if line.strip()]
    remaining = []
    for line in lines:
        path = line[3:].strip()
        if path in PROTECTED_UNTRACKED and line.startswith("?? "):
            continue
        remaining.append(line)
    if remaining:
        return "DIRTY", remaining
    if lines:
        return "CLEAN_WITH_PROTECTED_E1_UNTRACKED", []
    return "CLEAN", []


def main() -> int:
    parser = argparse.ArgumentParser(description="Génère les métadonnées réelles du build SEGYRCALC")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--distribution", default=DISTRIBUTION)
    parser.add_argument("--engine-source", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output.resolve()
    package_path = root / "frontend" / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    commit = git(root, "rev-parse", "HEAD")
    branch = git(root, "branch", "--show-current")
    state, dirty_lines = source_state(root)
    if state == "DIRTY":
        print("BUILD_SOURCE_STATE=DIRTY", file=sys.stderr)
        for line in dirty_lines:
            print(line, file=sys.stderr)
        return 3

    engine_source = args.engine_source or (
        root.parent.parent
        / "SEGYRCALC-V1.5-UI-ERGONOMIE-01"
        / "worktree"
        / "src"
        / "calcelect"
        / "service_v13.py"
    )
    engine_version = read_engine_version(engine_source)
    now = datetime.now(UTC)
    build_at = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    build_id = f"R63-{now.strftime('%Y%m%dT%H%M%SZ')}-{commit[:7]}"
    metadata = {
        "schema": "segyrcalc-build-metadata/v1",
        "build_id": build_id,
        "build_git_commit": commit,
        "build_at": build_at,
        "build_distribution": args.distribution,
        "application_version": package["version"],
        "engine_version": engine_version,
        "engine_entrypoint": "calcelect.service_v13.calculate_project_v13",
        "build_source_state": state,
        "build_source_branch": branch,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for key, value in metadata.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
