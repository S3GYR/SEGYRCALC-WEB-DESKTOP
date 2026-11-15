"""Read-only project catalog for the local SEGYRCALC interface.

The catalog reads only envelope metadata (identifier, administrative metadata,
client snapshot and electrical description). It never deserialises the full
electrical model, never invokes the calculation engine and never writes a file.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable, Literal

PROJECT_SUFFIXES = (
    ".segyrcalc-web.json",
    ".calcelect-v1.3.json",
    "-v1.3.json",
    ".calcelect-v1.4.json",
    "-v1.4.json",
)
MAX_CATALOG_FILE_BYTES = 20 * 1024 * 1024
PROGRESS_VALUES = ("NOT_DEFINED", "IN_PROGRESS", "COMPLETED")
SORTS = (
    "name_asc",
    "name_desc",
    "updated_desc",
    "updated_asc",
    "created_desc",
    "created_asc",
    "client_asc",
    "client_desc",
)
DEFAULT_SORT = "updated_desc"
DEFAULT_PAGE_SIZE = 25
ALLOWED_PAGE_SIZES = (25, 50, 100)


class CatalogError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    catalog_id: str
    path: Path
    project_id: str | None
    name: str
    reference: str
    client_id: str | None
    client_name: str
    description: str
    progress: str
    created_at: datetime | None
    updated_at: datetime | None
    file_modified: datetime
    format: str
    writable: bool
    metadata_error: str | None = None

    @property
    def search_text(self) -> str:
        return normalize_search(
            " ".join((self.name, self.reference, self.client_name, self.description))
        )

    def public(self) -> dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "project_id": self.project_id,
            "name": self.name,
            "reference": self.reference,
            "client_id": self.client_id,
            "client_name": self.client_name,
            "description": self.description,
            "progress": self.progress,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
            "file_modified": _iso(self.file_modified),
            "format": self.format,
            "writable": self.writable,
            "metadata_error": self.metadata_error,
        }


def normalize_search(value: str | None) -> str:
    """Normalise text for case/accent-insensitive literal substring search."""
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    )
    return " ".join(without_accents.casefold().split())


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_for(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".segyrcalc-web.json"):
        return "WEB-03"
    if name.endswith((".calcelect-v1.4.json", "-v1.4.json")):
        return "V1.4"
    return "V1.3"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _catalog_id(root_index: int, relative_path: str) -> str:
    material = f"{root_index}:{relative_path}".encode("utf-8", errors="replace")
    return hashlib.sha256(material).hexdigest()


def _is_reparse(path: Path) -> bool:
    try:
        stat = path.stat(follow_symlinks=False)
    except OSError:
        return True
    attributes = getattr(stat, "st_file_attributes", 0)
    return bool(attributes & 0x400) or path.is_symlink()


class ProjectCatalog:
    """Scan only the configured project roots and expose public metadata."""

    def __init__(self, root: Path, read_roots: Iterable[Path]) -> None:
        self.root = Path(root).expanduser().resolve()
        self.read_roots = tuple(dict.fromkeys(Path(item).expanduser().resolve() for item in read_roots))

    def _iter_paths(self) -> Iterable[tuple[int, Path, Path]]:
        for root_index, base in enumerate(self.read_roots):
            if not base.is_dir():
                continue
            for path in sorted(base.glob("*.json")):
                if not path.name.lower().endswith(PROJECT_SUFFIXES):
                    continue
                if _is_reparse(path) or not path.is_file():
                    continue
                yield root_index, base, path

    def _entry(self, root_index: int, base: Path, path: Path) -> CatalogEntry:
        relative = path.relative_to(base).as_posix()
        catalog_id = _catalog_id(root_index, relative)
        stat = None
        try:
            stat = path.stat()
            file_modified = datetime.fromtimestamp(stat.st_mtime, UTC)
        except OSError:
            file_modified = datetime.fromtimestamp(0, UTC)
        fallback_name = path.name
        if stat is None or stat.st_size > MAX_CATALOG_FILE_BYTES:
            return CatalogEntry(
                catalog_id=catalog_id,
                path=path,
                project_id=None,
                name=fallback_name,
                reference="",
                client_id=None,
                client_name="",
                description="",
                progress="NOT_DEFINED",
                created_at=None,
                updated_at=None,
                file_modified=file_modified,
                format=_format_for(path),
                writable=base == self.root,
                metadata_error="Fichier trop volumineux ou illisible",
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            return CatalogEntry(
                catalog_id=catalog_id,
                path=path,
                project_id=None,
                name=fallback_name,
                reference="",
                client_id=None,
                client_name="",
                description="",
                progress="NOT_DEFINED",
                created_at=None,
                updated_at=None,
                file_modified=file_modified,
                format=_format_for(path),
                writable=base == self.root,
                metadata_error="Métadonnées JSON illisibles",
            )

        document = _dict(payload)
        envelope_project = _dict(_dict(document.get("calcelect_v14")).get("project"))
        project = envelope_project or _dict(document.get("project"))
        electrical = _dict(project.get("electrical"))
        metadata = _dict(project.get("metadata"))
        snapshot = _dict(project.get("client_snapshot"))

        name = (
            _text(metadata.get("designation"))
            or _text(electrical.get("name"))
            or _text(project.get("name"))
            or fallback_name
        )
        reference = (
            _text(metadata.get("code"))
            or _text(electrical.get("reference"))
            or _text(project.get("reference"))
        )
        description = _text(electrical.get("description")) or _text(project.get("description"))
        client_id = (
            metadata.get("client_id")
            if isinstance(metadata.get("client_id"), str)
            else snapshot.get("client_id")
            if isinstance(snapshot.get("client_id"), str)
            else None
        )
        client_name = (
            _text(snapshot.get("company_name"))
            or _text(electrical.get("client"))
            or _text(project.get("client"))
        )
        progress = _text(metadata.get("progress")).upper()
        if progress not in PROGRESS_VALUES:
            progress = "NOT_DEFINED"
        created_at = _parse_datetime(metadata.get("created_at")) or _parse_datetime(
            electrical.get("created_at")
        ) or _parse_datetime(project.get("created_at"))
        updated_at = _parse_datetime(metadata.get("updated_at")) or _parse_datetime(
            electrical.get("updated_at")
        ) or _parse_datetime(project.get("updated_at"))
        project_id = project.get("project_id") or electrical.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            project_id = None
        return CatalogEntry(
            catalog_id=catalog_id,
            path=path,
            project_id=project_id,
            name=name,
            reference=reference,
            client_id=client_id,
            client_name=client_name,
            description=description,
            progress=progress,
            created_at=created_at,
            updated_at=updated_at,
            file_modified=file_modified,
            format=_format_for(path),
            writable=base == self.root,
        )

    def entries(self) -> list[CatalogEntry]:
        result: list[CatalogEntry] = []
        for root_index, base, path in self._iter_paths():
            result.append(self._entry(root_index, base, path))
        return result

    def query(
        self,
        *,
        q: str = "",
        client_id: str | None = None,
        progress: str | None = None,
        date_field: Literal["created", "updated"] = "updated",
        date_from: date | None = None,
        date_to: date | None = None,
        sort: str = DEFAULT_SORT,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any]:
        if date_from is not None and date_to is not None and date_from > date_to:
            raise CatalogError("DATE_RANGE_INVALIDE", "La date de début dépasse la date de fin.", 422)
        if sort not in SORTS:
            raise CatalogError("TRI_INVALIDE", "Tri de catalogue inconnu.", 422)
        if page < 1:
            raise CatalogError("PAGE_INVALIDE", "La page doit être supérieure ou égale à 1.", 422)
        if page_size not in ALLOWED_PAGE_SIZES:
            raise CatalogError("TAILLE_PAGE_INVALIDE", "Taille de page non autorisée.", 422)
        if progress is not None and progress not in PROGRESS_VALUES:
            raise CatalogError("PROGRESSION_INVALIDE", "Valeur de progression inconnue.", 422)

        terms = normalize_search(q).split()
        selected: list[CatalogEntry] = []
        for entry in self.entries():
            if terms and not all(term in entry.search_text for term in terms):
                continue
            if client_id and entry.client_id != client_id:
                continue
            if progress is not None and entry.progress != progress:
                continue
            if date_from is not None or date_to is not None:
                value = entry.created_at if date_field == "created" else entry.updated_at
                if value is None:
                    continue
                value_date = value.date()
                if date_from is not None and value_date < date_from:
                    continue
                if date_to is not None and value_date > date_to:
                    continue
            selected.append(entry)

        selected = self._sort_entries(selected, sort)
        total = len(selected)
        total_pages = (total + page_size - 1) // page_size if total else 0
        start = (page - 1) * page_size
        items = selected[start : start + page_size]
        return {
            "items": [item.public() for item in items],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        }

    def _sort_entries(self, entries: list[CatalogEntry], sort: str) -> list[CatalogEntry]:
        descending = sort.endswith("_desc")
        field = sort.rsplit("_", 1)[0]
        if field == "name":
            present = [item for item in entries if item.name]
            missing = [item for item in entries if not item.name]
            present.sort(key=lambda item: (normalize_search(item.name), item.catalog_id), reverse=descending)
        elif field == "client":
            present = [item for item in entries if item.client_name]
            missing = [item for item in entries if not item.client_name]
            present.sort(
                key=lambda item: (normalize_search(item.client_name), item.catalog_id),
                reverse=descending,
            )
        elif field in {"created", "updated"}:
            present = [
                item
                for item in entries
                if (item.created_at if field == "created" else item.updated_at) is not None
            ]
            missing = [
                item
                for item in entries
                if (item.created_at if field == "created" else item.updated_at) is None
            ]

            def date_key(item: CatalogEntry) -> tuple[datetime, str]:
                value = item.created_at if field == "created" else item.updated_at
                return (value or datetime.fromtimestamp(0, UTC), item.catalog_id)

            present.sort(key=date_key, reverse=descending)
        else:
            present = list(entries)
            missing = []
            present.sort(key=lambda item: (normalize_search(item.name), item.catalog_id))
        return present + missing

    def resolve(self, catalog_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", catalog_id):
            raise CatalogError("PROJET_INTROUVABLE", "Projet introuvable dans le catalogue.", 404)
        for root_index, base, path in self._iter_paths():
            relative = path.relative_to(base).as_posix()
            if _catalog_id(root_index, relative) == catalog_id:
                return path
        raise CatalogError("PROJET_INTROUVABLE", "Projet introuvable dans le catalogue.", 404)
