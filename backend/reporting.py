"""Report snapshot and export service for isolated WEB-06.

The report snapshot is built from the current WEB-05 payload only when the
calculation revision is current. PDF, XLSX and CSV all consume the same frozen
snapshot; no electrical formula is evaluated here.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

from .project_store import ProjectStoreError
from .runtime_paths import exports_root

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_ROOT = exports_root()
MAX_SNAPSHOTS = 20
DEFAULT_SECTIONS = (
    "cover",
    "general",
    "summary",
    "architecture",
    "boards",
    "feeders",
    "receivers",
    "coefficients",
    "phases",
    "assumptions",
    "traceability",
)


class ReportError(ProjectStoreError):
    pass


@dataclass(frozen=True, slots=True)
class ReportConfig:
    title: str = "Bilan de puissance électrique"
    sections: tuple[str, ...] = DEFAULT_SECTIONS
    orientation: Literal["portrait", "landscape"] = "portrait"
    decimals: int = 2
    units: str = "auto"
    csv_delimiter: Literal[";", ",", "\t"] = ";"
    include_assumptions: bool = True
    include_traceability: bool = True

    def __post_init__(self) -> None:
        title = self.title.strip()
        if not title or len(title) > 200:
            raise ReportError("TITRE_RAPPORT_INVALIDE", "Titre de rapport invalide.", 422)
        if self.orientation not in {"portrait", "landscape"}:
            raise ReportError("ORIENTATION_INVALIDE", "Orientation invalide.", 422)
        if not 0 <= self.decimals <= 6:
            raise ReportError("DECIMALES_INVALIDES", "Nombre de décimales invalide.", 422)
        if self.csv_delimiter not in {";", ",", "\t"}:
            raise ReportError("SEPARATEUR_CSV_INVALIDE", "Séparateur CSV invalide.", 422)
        unknown = set(self.sections) - set(DEFAULT_SECTIONS)
        if unknown:
            raise ReportError(
                "SECTION_INCONNUE",
                f"Sections inconnues: {', '.join(sorted(unknown))}",
                422,
            )
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "sections", tuple(dict.fromkeys(self.sections)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "sections": list(self.sections),
            "orientation": self.orientation,
            "decimals": self.decimals,
            "units": self.units,
            "csv_delimiter": self.csv_delimiter,
            "include_assumptions": self.include_assumptions,
            "include_traceability": self.include_traceability,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReportConfig:
        orientation = str(data.get("orientation") or "portrait")
        return cls(
            title=str(data.get("title") or "Bilan de puissance électrique"),
            sections=tuple(data.get("sections") or DEFAULT_SECTIONS),
            orientation=cast(Literal["portrait", "landscape"], orientation),
            decimals=int(data.get("decimals", 2)),
            units=str(data.get("units") or "auto"),
            csv_delimiter=cast(Literal[";", ",", "\t"], str(data.get("csv_delimiter") or ";")),
            include_assumptions=bool(data.get("include_assumptions", True)),
            include_traceability=bool(data.get("include_traceability", True)),
        )


@dataclass(frozen=True, slots=True)
class ReportSnapshot:
    snapshot_id: str
    created_at: datetime
    project_id: str
    project_name: str
    project_reference: str
    revision: int
    calculation_revision: int | None
    source_sha256: str
    payload: dict[str, Any]
    config: ReportConfig

    def meta(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at.isoformat(),
            "project_id": self.project_id,
            "project_name": self.project_name,
            "project_reference": self.project_reference,
            "revision": self.revision,
            "calculation_revision": self.calculation_revision,
            "source_sha256": self.source_sha256,
            "config": self.config.to_dict(),
            "engine": self.payload.get("engine", {}),
            "coherence": self.payload.get("coherence", {}),
        }


def _canonical_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _rows(payload: dict[str, Any], config: ReportConfig) -> dict[str, list[dict[str, Any]]]:
    boards = [
        {
            "reference": item.get("id"),
            "designation": item.get("designation"),
            "type": item.get("type"),
            "network": item.get("network"),
            "voltage_v": item.get("voltage_v"),
            "feeders": item.get("feeder_count"),
            "receivers": item.get("load_count"),
            "p_installed_w": item.get("p_installed_w"),
            "p_after_ku_w": item.get("p_after_ku_w"),
            "p_after_ks_w": item.get("p_after_ks_w"),
            "q_after_ku_var": item.get("q_after_ku_var"),
            "q_after_ks_var": item.get("q_after_ks_var"),
            "s_after_ku_va": item.get("s_after_ku_va"),
            "s_after_ks_va": item.get("s_after_ks_va"),
            "neutral_current_a": item.get("neutral_current_a"),
            "unbalance_percent": item.get("unbalance_percent"),
            "status": item.get("status"),
        }
        for item in payload.get("boards", [])
    ]
    feeders = [
        {
            "reference": item.get("id"),
            "designation": item.get("designation"),
            "board": item.get("parent_board_id"),
            "network": item.get("network"),
            "voltage_v": item.get("voltage_v"),
            "receivers": item.get("member_count"),
            "ks": item.get("ks"),
            "p_installed_w": item.get("p_installed_w"),
            "p_after_ku_w": item.get("p_after_ku_w"),
            "p_after_ks_w": item.get("p_after_ks_w"),
            "q_after_ku_var": item.get("q_after_ku_var"),
            "q_after_ks_var": item.get("q_after_ks_var"),
            "s_after_ku_va": item.get("s_after_ku_va"),
            "s_after_ks_va": item.get("s_after_ks_va"),
            "neutral_current_a": item.get("neutral_current_a"),
            "unbalance_percent": item.get("unbalance_percent"),
            "status": item.get("status"),
        }
        for item in payload.get("feeders", [])
    ]
    receivers = [
        {
            "reference": item.get("id"),
            "designation": item.get("designation"),
            "board": item.get("parent_board_id"),
            "feeder": item.get("feeder_id"),
            "network": item.get("network"),
            "voltage_v": item.get("voltage_v"),
            "quantity": item.get("quantity"),
            "installed_power_w": item.get("installed_power_w"),
            "power_factor": item.get("power_factor"),
            "ku": item.get("ku"),
            "ks": item.get("ks"),
            "p_after_ku_w": item.get("p_after_ku_w"),
            "p_after_ks_w": item.get("p_after_ks_w"),
            "q_after_ku_var": item.get("q_after_ku_var"),
            "q_after_ks_var": item.get("q_after_ks_var"),
            "s_after_ks_va": item.get("s_after_ks_va"),
            "current_a": item.get("current_a"),
            "phase": item.get("phase"),
            "status": item.get("status"),
            "s_available": bool(item.get("apparent_power_available")),
            "i_available": bool(item.get("current_available")),
        }
        for item in payload.get("loads", [])
    ]
    return {"boards": boards, "feeders": feeders, "receivers": receivers}


def build_preview(snapshot: ReportSnapshot) -> dict[str, Any]:
    payload = snapshot.payload
    rows = _rows(payload, snapshot.config)
    totals = payload.get("totals", {})
    return {
        "snapshot": snapshot.meta(),
        "summary": {
            "project": payload.get("project", {}),
            "totals": totals,
            "status": payload.get("status"),
            "is_calculable": payload.get("is_calculable"),
            "calculated_at": payload.get("calculated_at"),
        },
        "boards": rows["boards"],
        "feeders": rows["feeders"],
        "receivers": rows["receivers"],
        "phases": {
            "p": totals.get("p_phases"),
            "q": totals.get("q_phases"),
            "s": totals.get("s_phases"),
            "i": totals.get("current_phases"),
            "neutral": totals.get("neutral_current_a"),
            "unbalance": totals.get("unbalance_percent"),
        },
        "assumptions": payload.get("assumptions", []),
        "diagnostics": payload.get("diagnostics", []),
        "coherence": payload.get("coherence", {}),
        "traceability": {
            "engine": payload.get("engine", {}),
            "revision": snapshot.revision,
            "calculation_revision": snapshot.calculation_revision,
            "source_sha256": snapshot.source_sha256,
            "calculated_at": payload.get("calculated_at"),
        },
        "config": snapshot.config.to_dict(),
    }


class ReportService:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or EXPORT_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.snapshots: OrderedDict[str, ReportSnapshot] = OrderedDict()

    def create_snapshot(self, store: Any, config: ReportConfig) -> ReportSnapshot:
        if store.project is None:
            raise ReportError("AUCUN_PROJET", "Aucun projet ouvert.", 404)
        state = store.state
        if state.get("calculation_revision") != state.get("revision"):
            raise ReportError(
                "RAPPORT_REVISION_PERIMEE",
                "Le résultat courant n'est pas calculé pour la révision active.",
                409,
            )
        payload = store._payload()
        project = payload.get("project", {})
        revision = int(state.get("revision", 0))
        calculation_revision = state.get("calculation_revision")
        snapshot = ReportSnapshot(
            snapshot_id=str(uuid4()),
            created_at=datetime.now(UTC),
            project_id=str(project.get("id", "")),
            project_name=str(project.get("name", "")),
            project_reference=str(project.get("reference", "")),
            revision=revision,
            calculation_revision=calculation_revision,
            source_sha256=_canonical_hash(payload),
            payload=payload,
            config=config,
        )
        self.snapshots[snapshot.snapshot_id] = snapshot
        while len(self.snapshots) > MAX_SNAPSHOTS:
            self.snapshots.popitem(last=False)
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> ReportSnapshot:
        snapshot = self.snapshots.get(snapshot_id)
        if snapshot is None:
            raise ReportError("SNAPSHOT_INTROUVABLE", "Snapshot de rapport introuvable.", 404)
        return snapshot

    def preview(self, store: Any, config: ReportConfig) -> dict[str, Any]:
        snapshot = self.create_snapshot(store, config)
        return build_preview(snapshot)

    def export(
        self,
        snapshot_id: str,
        format_name: str,
        path: Path,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        snapshot = self.get_snapshot(snapshot_id)
        fmt = format_name.lower()
        if fmt == "pdf":
            from .report_pdf import generate_pdf

            target = self._resolve_file_path(path, ".pdf")
            if target.exists() and not overwrite:
                raise ReportError("FICHIER_EXISTE", "Le fichier existe déjà.", 409)
            data = generate_pdf(snapshot)
            self._atomic_write(target, data)
            return {
                "format": "pdf",
                "files": [
                    {
                        "path": str(target),
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest().upper(),
                    }
                ],
            }
        if fmt == "xlsx":
            from .report_xlsx import generate_xlsx

            target = self._resolve_file_path(path, ".xlsx")
            if target.exists() and not overwrite:
                raise ReportError("FICHIER_EXISTE", "Le fichier existe déjà.", 409)
            data = generate_xlsx(snapshot)
            self._atomic_write(target, data)
            return {
                "format": "xlsx",
                "files": [
                    {
                        "path": str(target),
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest().upper(),
                    }
                ],
            }
        if fmt == "csv":
            from .report_csv import generate_csv_files

            target_dir = self._resolve_dir_path(path)
            files = generate_csv_files(snapshot)
            targets = {name: target_dir / name for name in files}
            for target in targets.values():
                if target.exists() and target.is_dir():
                    raise ReportError(
                        "DESTINATION_INVALIDE",
                        "Une destination CSV est un répertoire.",
                        422,
                    )
            if not overwrite:
                existing = [name for name, target in targets.items() if target.exists()]
                if existing:
                    raise ReportError(
                        "FICHIER_EXISTE",
                        f"Fichiers CSV existants: {', '.join(sorted(existing))}.",
                        409,
                    )
            self._atomic_write_many({targets[name]: data for name, data in files.items()})
            results = [
                {
                    "path": str(targets[name]),
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest().upper(),
                }
                for name, data in files.items()
            ]
            return {"format": "csv", "files": results}
        raise ReportError("FORMAT_EXPORT_INVALIDE", "Format d'export invalide.", 415)

    def _resolve_file_path(self, path: Path, suffix: str) -> Path:
        requested = path.expanduser()
        if not requested.is_absolute():
            raise ReportError(
                "CHEMIN_ABSOLU_REQUIS",
                "Le chemin d'export doit être absolu.",
                422,
            )
        try:
            resolved = requested.resolve()
        except OSError as exc:
            raise ReportError(
                "CHEMIN_INVALIDE",
                f"Chemin d'export invalide: {exc}",
                422,
            ) from exc
        if resolved.suffix.lower() != suffix:
            raise ReportError("EXTENSION_NON_AUTORISEE", f"Extension attendue: {suffix}", 415)
        if resolved.exists() and resolved.is_dir():
            raise ReportError(
                "DESTINATION_INVALIDE",
                "La destination est un répertoire, pas un fichier.",
                422,
            )
        return resolved

    def _resolve_dir_path(self, path: Path) -> Path:
        requested = path.expanduser()
        if not requested.is_absolute():
            raise ReportError(
                "CHEMIN_ABSOLU_REQUIS",
                "Le répertoire d'export doit être absolu.",
                422,
            )
        try:
            resolved = requested.resolve()
        except OSError as exc:
            raise ReportError(
                "CHEMIN_INVALIDE",
                f"Répertoire d'export invalide: {exc}",
                422,
            ) from exc
        if resolved.exists() and not resolved.is_dir():
            raise ReportError(
                "DESTINATION_INVALIDE",
                "La destination existe déjà et n'est pas un répertoire.",
                422,
            )
        return resolved

    def _atomic_write(self, path: Path, data: bytes) -> None:
        temp: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
            )
            temp = Path(temp_name)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if temp.stat().st_size != len(data):
                raise ReportError(
                    "ECRITURE_INCOMPLETE",
                    "Le fichier temporaire est incomplet.",
                    422,
                )
            os.replace(temp, path)
            if not path.is_file() or path.stat().st_size != len(data):
                raise ReportError(
                    "ECRITURE_NON_CONFIRMEE",
                    "Le fichier final n'a pas été confirmé.",
                    422,
                )
        except ReportError:
            raise
        except OSError as exc:
            raise ReportError(
                "ECRITURE_IMPOSSIBLE",
                f"Impossible d'écrire le fichier à l'emplacement choisi: {exc}",
                422,
            ) from exc
        finally:
            if temp is not None and temp.exists():
                temp.unlink(missing_ok=True)

    def _atomic_write_many(self, targets: dict[Path, bytes]) -> None:
        temps: dict[Path, Path] = {}
        backups: dict[Path, Path] = {}
        installed: set[Path] = set()

        def rollback() -> None:
            for path in installed:
                path.unlink(missing_ok=True)
            for path, backup in backups.items():
                if backup.exists():
                    os.replace(backup, path)
            for temp in temps.values():
                temp.unlink(missing_ok=True)

        try:
            for path, data in targets.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists() and path.is_dir():
                    raise ReportError(
                        "DESTINATION_INVALIDE",
                        "Une destination CSV est un répertoire.",
                        422,
                    )
                fd, temp_name = tempfile.mkstemp(
                    dir=path.parent,
                    prefix=f".{path.name}.",
                    suffix=".tmp",
                )
                temp = Path(temp_name)
                temps[path] = temp
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                if temp.stat().st_size != len(data):
                    raise ReportError(
                        "ECRITURE_INCOMPLETE",
                        "Un fichier CSV temporaire est incomplet.",
                        422,
                    )
            for path in targets:
                if path.exists():
                    backup = path.with_name(f".{path.name}.{uuid4().hex}.bak")
                    os.replace(path, backup)
                    backups[path] = backup
            for path, temp in temps.items():
                os.replace(temp, path)
                installed.add(path)
            for path, data in targets.items():
                if not path.is_file() or path.stat().st_size != len(data):
                    raise ReportError(
                        "ECRITURE_NON_CONFIRMEE",
                        "Un fichier CSV final n'a pas été confirmé.",
                        422,
                    )
        except ReportError:
            rollback()
            raise
        except OSError as exc:
            rollback()
            raise ReportError(
                "ECRITURE_IMPOSSIBLE",
                f"Impossible d'écrire les fichiers CSV à l'emplacement choisi: {exc}",
                422,
            ) from exc
        else:
            for backup in backups.values():
                backup.unlink(missing_ok=True)
        finally:
            for temp in temps.values():
                temp.unlink(missing_ok=True)

    def list_exports(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            entries.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                    "suffix": path.suffix.lower(),
                }
            )
        return entries[-100:]


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
