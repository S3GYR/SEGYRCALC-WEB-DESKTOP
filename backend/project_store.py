"""Isolated WEB-04 project store (WEB-03 compatibility retained).

The electrical model is the existing ProjectV14 / ProjectV11 model. The WEB-03
envelope only adds UI metadata around that model; it is not a second electrical
model and it never modifies a historical file.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

# engine_adapter installs the read-only V1.5 source path before these imports.
from calcelect.clients.normalization import utc_now
from calcelect.hierarchy import Board, BoardType, Feeder, LoadAssignment, ProjectV11
from calcelect.models import LoadEntry
from calcelect.persistence_v13 import load_project_v13
from calcelect.persistence_v14 import load_project_v14, project_from_dict_v14, project_to_dict_v14
from calcelect.project_v14 import ClientSnapshot, ProjectMetadataV14, ProjectV14
from calcelect.sources.models import SourceV14
from calcelect.service_v13 import calculate_project_v13
from segyr_calc.a2.models import Load
from segyr_calc.core.power import Network

from .client_store import ClientStore, ClientStoreError
from .distribution import DistributionError, resolve_distribution
from .project_payload import build_project_payload
from .runtime_paths import projects_root

WEB_SCHEMA = "SEGYRCALC_WEB_PROJECT"
WEB_VERSION = "0.3.0"
SOURCE_WEB_VERSION = "0.3.1"
SUPPORTED_WEB_VERSIONS = frozenset({WEB_VERSION, SOURCE_WEB_VERSION})
WEB_SUFFIX = ".segyrcalc-web.json"
MAX_PROJECT_BYTES = 20 * 1024 * 1024
DEFAULT_STANDARD = "NF C 15-100"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUALIFICATION_ROOT = projects_root()
WORKTREE = PROJECT_ROOT.parent.parent / "SEGYRCALC-V1.5-UI-ERGONOMIE-01" / "worktree"
READ_ROOTS = (
    DEFAULT_QUALIFICATION_ROOT,
    WORKTREE / "examples",
    WORKTREE / "fixtures",
)


class ProjectStoreError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class WebMetadata:
    site: str = ""
    address: str = ""
    observations: str = ""
    created_by: str = ""
    application: str = "SEGYRCALC Web Desktop"
    format_version: str = WEB_VERSION

    def __post_init__(self) -> None:
        if (
            len(self.site) > 500
            or len(self.address) > 500
            or len(self.observations) > 4000
            or len(self.created_by) > 200
        ):
            raise ProjectStoreError("METADONNEES_WEB_INVALIDES", "Métadonnées WEB trop longues.")
        if self.format_version not in SUPPORTED_WEB_VERSIONS:
            raise ProjectStoreError("VERSION_WEB_INVALIDE", "Version de format WEB incompatible.")

    def to_dict(self) -> dict[str, str]:
        return {
            "site": self.site,
            "address": self.address,
            "observations": self.observations,
            "created_by": self.created_by,
            "application": self.application,
            "format_version": self.format_version,
        }

    @classmethod
    def from_dict(cls, data: object) -> WebMetadata:
        if not isinstance(data, dict):
            raise ProjectStoreError("METADONNEES_WEB_INVALIDES", "Bloc web invalide.")
        allowed = {"site", "address", "observations", "created_by", "application", "format_version"}
        if set(data) != allowed:
            raise ProjectStoreError(
                "METADONNEES_WEB_INVALIDES", "Clés web inconnues ou manquantes."
            )
        values = {key: data[key] for key in allowed}
        if any(not isinstance(value, str) for value in values.values()):
            raise ProjectStoreError(
                "METADONNEES_WEB_INVALIDES", "Les métadonnées web doivent être textuelles."
            )
        return cls(**values)


def _json_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Clé JSON dupliquée: {key}")
        result[key] = value
    return result


def serialize_web_project(
    project: ProjectV14,
    web: WebMetadata,
    feeder_references: dict[str, str] | None = None,
) -> bytes:
    version = SOURCE_WEB_VERSION if project.source is not None else WEB_VERSION
    web_payload = web.to_dict()
    web_payload["format_version"] = version
    serialized_project = project_to_dict_v14(project)
    if project.source is not None and serialized_project["project"].get("source") is None:
        raise ProjectStoreError(
            "SOURCE_PERDUE",
            "La sauvegarde ne peut pas garantir la conservation de la source.",
            409,
        )
    payload: dict[str, Any] = {
        "schema": WEB_SCHEMA,
        "schema_version": version,
        "web": web_payload,
        "calcelect_v14": serialized_project,
    }
    cleaned_references = {
        feeder_id: _normalized_reference(reference)
        for feeder_id, reference in (feeder_references or {}).items()
        if feeder_id in project.electrical.feeder_map()
        and _normalized_reference(reference)
    }
    if cleaned_references:
        payload["feeder_references"] = cleaned_references
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def deserialize_web_project(
    data: bytes,
) -> tuple[ProjectV14, WebMetadata, dict[str, str]]:
    if len(data) > MAX_PROJECT_BYTES:
        raise ProjectStoreError("PROJET_TROP_VOLUMINEUX", "Le fichier projet dépasse la limite.")
    try:
        text = data.decode("utf-8")
        payload = json.loads(text, object_pairs_hook=_json_no_duplicates)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ProjectStoreError("PROJET_JSON_INVALIDE", f"JSON projet invalide: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProjectStoreError(
            "PROJET_JSON_INVALIDE", "Le document projet doit être un objet JSON."
        )
    allowed_envelope = {"schema", "schema_version", "web", "calcelect_v14"}
    if set(payload) not in (allowed_envelope, allowed_envelope | {"feeder_references"}):
        raise ProjectStoreError("PROJET_JSON_INVALIDE", "Structure d'enveloppe WEB-03 invalide.")
    if payload["schema"] != WEB_SCHEMA or payload["schema_version"] not in SUPPORTED_WEB_VERSIONS:
        raise ProjectStoreError(
            "PROJET_VERSION_INVALIDE", "Schéma ou version WEB-03 non pris en charge."
        )
    web = WebMetadata.from_dict(payload["web"])
    if web.format_version != payload["schema_version"]:
        raise ProjectStoreError(
            "PROJET_VERSION_INVALIDE", "Version d'enveloppe WEB incohérente."
        )
    try:
        project = project_from_dict_v14(payload["calcelect_v14"])
    except Exception as exc:
        raise ProjectStoreError(
            "PROJET_V14_INVALIDE", f"Projet V1.4 embarqué invalide: {exc}"
        ) from exc
    references = _feeder_references_from_payload(payload.get("feeder_references"), project)
    return project, web, references


def _model_error(exc: Exception) -> ProjectStoreError:
    code = str(getattr(exc, "code", "PROJET_INVALIDE"))
    message = str(getattr(exc, "message", str(exc)))
    return ProjectStoreError(code, message, 422)


_REFERENCE_RE = re.compile(r"^Q([1-9][0-9]*)$")
_REFERENCE_MAX_LENGTH = 50


def _normalized_reference(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > _REFERENCE_MAX_LENGTH:
        raise ProjectStoreError(
            "REPERE_DEPART_INVALIDE",
            "Le repère du départ est trop long.",
            422,
        )
    return text


def _effective_feeder_reference(
    feeder: Feeder,
    references: dict[str, str],
) -> str:
    reference = _normalized_reference(references.get(feeder.feeder_id))
    if reference:
        return reference
    legacy = str(feeder.designation).strip()
    return legacy if _REFERENCE_RE.fullmatch(legacy) else ""


def _next_feeder_reference(
    electrical: ProjectV11,
    parent_board_id: str,
    references: dict[str, str],
    *,
    exclude_feeder_id: str | None = None,
) -> str:
    highest = 0
    used: set[str] = set()
    for feeder in electrical.feeders_of(parent_board_id):
        if feeder.feeder_id == exclude_feeder_id:
            continue
        reference = _effective_feeder_reference(feeder, references)
        if not reference:
            continue
        used.add(reference)
        match = _REFERENCE_RE.fullmatch(reference)
        if match is not None:
            highest = max(highest, int(match.group(1)))
    number = highest + 1
    while f"Q{number}" in used:
        number += 1
    return f"Q{number}"


def _check_feeder_reference(
    electrical: ProjectV11,
    parent_board_id: str,
    reference: str,
    references: dict[str, str],
    *,
    exclude_feeder_id: str | None = None,
) -> None:
    if not reference:
        return
    for feeder in electrical.feeders_of(parent_board_id):
        if feeder.feeder_id == exclude_feeder_id:
            continue
        existing = _effective_feeder_reference(feeder, references)
        if existing == reference:
            raise ProjectStoreError(
                "REPERE_DEPART_DUPLIQUE",
                f"Le repère {reference} est déjà utilisé dans ce tableau.",
                422,
            )


def _feeder_references_from_payload(
    value: object,
    project: ProjectV14,
) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ProjectStoreError(
            "REPERES_DEPARTS_INVALIDES",
            "Le registre des repères de départs est invalide.",
        )
    feeder_ids = set(project.electrical.feeder_map())
    references: dict[str, str] = {}
    for feeder_id, raw_reference in value.items():
        if not isinstance(feeder_id, str) or not isinstance(raw_reference, str):
            raise ProjectStoreError(
                "REPERES_DEPARTS_INVALIDES",
                "Le registre des repères de départs est invalide.",
            )
        if feeder_id not in feeder_ids:
            continue
        reference = _normalized_reference(raw_reference)
        if reference:
            references[feeder_id] = reference
    return references


def _next_id(prefix: str, existing: set[str]) -> str:
    highest = 0
    for value in existing:
        if value.startswith(prefix):
            suffix = value[len(prefix) :].lstrip("-")
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return f"{prefix}-{highest + 1:02d}"


def _client_snapshot(client: str, address: str) -> ClientSnapshot | None:
    if not client.strip():
        return None
    return ClientSnapshot(
        client_id=None,
        company_name=client,
        address=address,
        country="",
        contact_name="",
        email="",
        phone="",
        logo=None,
        captured_at=utc_now(),
    )


def _web_client_info(path: Path) -> tuple[str | None, str]:
    """Read optional client metadata without mutating a project file."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        project = payload.get("calcelect_v14", {}).get("project", {})
        metadata = project.get("metadata", {}) if isinstance(project, dict) else {}
        snapshot = project.get("client_snapshot", {}) if isinstance(project, dict) else {}
        client_id = metadata.get("client_id") if isinstance(metadata, dict) else None
        company = snapshot.get("company_name", "") if isinstance(snapshot, dict) else ""
        return (
            client_id if isinstance(client_id, str) else None,
            company if isinstance(company, str) else "",
        )
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
        return None, ""


_PHASE_CODES = {"L1", "L2", "L3"}


def _phase_text(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    if raw is None:
        return None
    text = str(raw).strip().upper()
    return text or None


def _feeder_has_neutral(feeder: Feeder, board: Board | None) -> bool:
    if feeder.has_neutral is not None:
        return bool(feeder.has_neutral)
    return bool(board and board.has_neutral)


def _validated_phase(value: Any) -> str | None:
    phase = _phase_text(value)
    if phase is not None and phase not in _PHASE_CODES:
        raise ProjectStoreError(
            "PHASE_INVALIDE",
            "La phase doit être L1, L2 ou L3.",
            422,
        )
    return phase


def _phase_for_new_load(
    feeder: Feeder,
    board: Board | None,
    network: str,
    requested: Any,
) -> str | None:
    phase = _validated_phase(requested)
    if feeder.network is Network.MONO:
        if network != "MONO":
            raise ProjectStoreError(
                "PHASE_INCOMPATIBLE",
                "Un départ monophasé ne peut alimenter qu'un récepteur monophasé.",
                422,
            )
        inherited = _phase_text(feeder.phase)
        if phase is not None and phase != inherited:
            raise ProjectStoreError(
                "PHASE_INCOMPATIBLE",
                "La phase du récepteur doit être celle du départ monophasé.",
                422,
            )
        return inherited
    if network == "MONO":
        if not _feeder_has_neutral(feeder, board):
            raise ProjectStoreError(
                "NEUTRE_ABSENT",
                "Le départ ne dispose pas du neutre requis pour un récepteur phase-neutre.",
                422,
            )
        return phase
    if phase is not None:
        raise ProjectStoreError(
            "PHASE_INVALIDE",
            "Un récepteur triphasé ne porte pas de phase unique.",
            422,
        )
    return None


def _phase_for_updated_load(
    feeder: Feeder,
    board: Board | None,
    network: str,
    requested: Any,
    current_phase: Any,
) -> str | None:
    phase = _validated_phase(requested)
    if feeder.network is Network.MONO:
        if network != "MONO":
            raise ProjectStoreError(
                "PHASE_INCOMPATIBLE",
                "Un départ monophasé ne peut alimenter qu'un récepteur monophasé.",
                422,
            )
        inherited = _phase_text(feeder.phase)
        return phase if phase is not None else inherited
    if network == "MONO":
        if not _feeder_has_neutral(feeder, board):
            raise ProjectStoreError(
                "NEUTRE_ABSENT",
                "Le départ ne dispose pas du neutre requis pour un récepteur phase-neutre.",
                422,
            )
        return phase if phase is not None else _phase_text(current_phase)
    if phase is not None:
        raise ProjectStoreError(
            "PHASE_INVALIDE",
            "Un récepteur triphasé ne porte pas de phase unique.",
            422,
        )
    return None


def _root_board(network: str, voltage_v: str, has_neutral: bool, voltage_ln_v: str | None) -> Board:
    return Board(
        board_id="TGBT-01",
        designation="TGBT principal",
        board_type=BoardType.TGBT,
        network=network,
        voltage_v=voltage_v,
        has_neutral=has_neutral,
        voltage_ln_v=voltage_ln_v,
    )


class ProjectStore:
    def __init__(
        self,
        root: Path | None = None,
        read_roots: tuple[Path, ...] | None = None,
        client_store: ClientStore | None = None,
    ) -> None:
        self.root = (root or DEFAULT_QUALIFICATION_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        defaults = tuple(path.resolve() for path in (read_roots or READ_ROOTS))
        self.read_roots = tuple(dict.fromkeys((self.root, *defaults)))
        self.client_store = client_store
        self.lock = threading.RLock()
        self.project: ProjectV14 | None = None
        self.web = WebMetadata()
        self.feeder_references: dict[str, str] = {}
        self.path: Path | None = None
        self.read_only_source = False
        self.source_format = "NONE"
        self.dirty = False
        self.revision = 0
        self.calculation_revision: int | None = None
        self.calculation: Any | None = None
        self.last_error: str | None = None

    @property
    def state(self) -> dict[str, Any]:
        return {
            "dirty": self.dirty,
            "revision": self.revision,
            "calculation_revision": self.calculation_revision,
            "stale": self.calculation_revision != self.revision,
            "file_path": str(self.path) if self.path else None,
            "read_only_source": self.read_only_source,
            "source_format": self.source_format,
            "last_error": self.last_error,
        }

    def _snapshot_for_client(
        self,
        client_id: str | None,
        client: str,
        address: str,
    ) -> ClientSnapshot | None:
        if not client_id:
            return _client_snapshot(client, address)
        if self.client_store is None:
            raise ProjectStoreError(
                "CLIENT_STORE_INDISPONIBLE",
                "Le référentiel client n'est pas disponible.",
                503,
            )
        try:
            return self.client_store.snapshot(client_id)
        except ClientStoreError as exc:
            raise ProjectStoreError(exc.code, exc.message, exc.status_code) from exc

    def _payload(self) -> dict[str, Any]:
        if self.project is None:
            raise ProjectStoreError("AUCUN_PROJET", "Aucun projet n'est ouvert.", 404)
        snapshot = self.project.client_snapshot
        payload = build_project_payload(
            self.project.electrical,
            self.calculation,
            web=self.web.to_dict(),
            state=self.state,
            data_class="WEB04_PROJECT",
            client_id=self.project.metadata.client_id,
            client_snapshot=snapshot.to_dict() if snapshot is not None else None,
        )
        payload["source"] = self.project.source.to_dict() if self.project.source is not None else None
        payload["format_version"] = self.web.to_dict()["format_version"]
        for feeder_payload in payload.get("feeders", []):
            feeder_payload["reference"] = self.feeder_references.get(
                str(feeder_payload.get("id")), ""
            )
        return payload

    def _recalculate(self) -> None:
        assert self.project is not None
        try:
            self.calculation = calculate_project_v13(self.project.electrical)
            self.calculation_revision = self.revision
            self.last_error = None
        except Exception as exc:
            self.calculation = None
            self.calculation_revision = None
            self.last_error = f"{getattr(exc, 'code', 'CALCUL_ECHOUE')}: {exc}"

    def _touch(self) -> None:
        self.revision += 1
        self.dirty = True
        self._recalculate()

    def _require_project(self) -> ProjectV14:
        if self.project is None:
            raise ProjectStoreError("AUCUN_PROJET", "Aucun projet n'est ouvert.", 404)
        return self.project
    def update_source(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            raw = payload.get("source")
            try:
                source = None if raw is None else SourceV14.from_dict(raw)
            except Exception as exc:
                raise ProjectStoreError(
                    "SOURCE_INVALIDE",
                    f"La source électrique est invalide: {exc}",
                    422,
                ) from exc
            self.project = replace(project, source=source)
            self.web = replace(
                self.web,
                format_version=SOURCE_WEB_VERSION if source is not None else WEB_VERSION,
            )
            self._touch()
            return self._payload()


    def new(
        self,
        *,
        name: str,
        reference: str,
        client: str = "",
        client_id: str | None = None,
        site: str = "",
        address: str = "",
        author: str = "",
        description: str = "",
        observations: str = "",
        revision: str = "A",
        standard: str = DEFAULT_STANDARD,
        network: str = "TRI",
        voltage_v: str = "400",
        has_neutral: bool = True,
        voltage_ln_v: str | None = "230",
    ) -> dict[str, Any]:
        with self.lock:
            try:
                snapshot = self._snapshot_for_client(client_id, client, address)
                snapshot_client = snapshot.company_name if snapshot is not None else client
                metadata = ProjectMetadataV14.new(
                    code=reference,
                    designation=name,
                    author=author,
                    client_id=client_id,
                    revision=revision,
                    standard=standard,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                electrical = ProjectV11.new(
                    name=name,
                    reference=reference,
                    client=snapshot_client,
                    description=description,
                ).add_board(_root_board(network, voltage_v, has_neutral, voltage_ln_v))
                self.project = ProjectV14(
                    electrical=electrical,
                    metadata=metadata,
                    client_snapshot=snapshot,
                    source=None,
                    enedis=None,
                )
                self.web = WebMetadata(
                    site=site,
                    address=address,
                    observations=observations,
                    created_by=author,
                )
                self.feeder_references = {}
                self.path = None
                self.read_only_source = False
                self.source_format = "WEB-03"
                self.dirty = True
                self.revision = 1
                self.calculation_revision = None
                self.calculation = None
                self.last_error = None
                self._recalculate()
                return self._payload()
            except ProjectStoreError:
                raise
            except Exception as exc:
                raise _model_error(exc) from exc

    def open(self, path: Path) -> dict[str, Any]:
        with self.lock:
            resolved = self._resolve_read_path(path)
            try:
                if resolved.name.endswith(WEB_SUFFIX):
                    data = resolved.read_bytes()
                    project, web, references = deserialize_web_project(data)
                    source_format = "WEB-03"
                    read_only = not _is_under(resolved, self.root)
                elif resolved.name.endswith((".calcelect-v1.4.json", "-v1.4.json")):
                    project = load_project_v14(resolved)
                    web = WebMetadata(
                        address=project.client_snapshot.address if project.client_snapshot else "",
                        created_by=project.metadata.author,
                    )
                    references = {}
                    source_format = "V1.4"
                    read_only = True
                elif resolved.name.endswith((".calcelect-v1.3.json", "-v1.3.json")):
                    v13 = load_project_v13(resolved)
                    project = ProjectV14.from_v13(v13)
                    web = WebMetadata(created_by="")
                    references = {}
                    source_format = "V1.3"
                    read_only = True
                else:
                    raise ProjectStoreError(
                        "FORMAT_NON_PRIS_EN_CHARGE", "Format de projet non pris en charge.", 415
                    )
            except ProjectStoreError:
                raise
            except Exception as exc:
                raise ProjectStoreError(
                    "PROJET_LECTURE_ECHEC", f"Lecture du projet impossible: {exc}", 422
                ) from exc
            self.project = project
            self.web = web
            self.feeder_references = references
            self.path = resolved
            self.read_only_source = read_only
            self.source_format = source_format
            self.dirty = False
            self.revision = 1
            self.calculation_revision = None
            self.calculation = None
            self.last_error = None
            self._recalculate()
            return self._payload()

    def save(self, path: Path | None = None, *, overwrite: bool = False) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            target = self.path if path is None else path
            if target is None:
                raise ProjectStoreError("CHEMIN_REQUIS", "Aucun chemin de sauvegarde.", 400)
            if self.read_only_source and path is None:
                raise ProjectStoreError(
                    "PROJET_HISTORIQUE_LECTURE_SEULE",
                    "Un projet historique doit être enregistré sous un nouveau nom.",
                    409,
                )
            target = self._resolve_write_path(target)
            data = serialize_web_project(project, self.web, self.feeder_references)
            self._atomic_write(target, data, overwrite=overwrite)
            self.web = replace(
                self.web,
                format_version=SOURCE_WEB_VERSION if project.source is not None else WEB_VERSION,
            )
            self.path = target
            self.read_only_source = False
            self.source_format = "WEB-03"
            self.dirty = False
            self.last_error = None
            return self._payload()

    def save_as(self, path: Path, *, overwrite: bool = False) -> dict[str, Any]:
        return self.save(path, overwrite=overwrite)

    def duplicate(self, path: Path, *, overwrite: bool = False) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            target = self._resolve_write_path(path)
            now = datetime.now(UTC)
            now_seconds = now.replace(microsecond=0)
            try:
                copied = replace(
                    project,
                    electrical=replace(
                        project.electrical,
                        project_id=str(uuid4()),
                        name=f"{project.electrical.name} (copie)",
                        created_at=now_seconds,
                        updated_at=now_seconds,
                    ),
                    metadata=replace(
                        project.metadata,
                        designation=f"{project.metadata.designation} (copie)",
                        updated_at=now,
                    ),
                )
                data = serialize_web_project(copied, self.web, self.feeder_references)
                self.web = replace(
                    self.web,
                    format_version=SOURCE_WEB_VERSION if copied.source is not None else WEB_VERSION,
                )
                original = self.project
                self.project = copied
                try:
                    self._atomic_write(target, data, overwrite=overwrite)
                except Exception:
                    self.project = original
                    raise
                self.path = target
                self.read_only_source = False
                self.source_format = "WEB-03"
                self.dirty = False
                self.revision = 1
                self.calculation_revision = None
                self.calculation = None
                self.last_error = None
                self._recalculate()
                return self._payload()
            except ProjectStoreError:
                raise
            except Exception as exc:
                raise _model_error(exc) from exc

    def close(self) -> dict[str, Any]:
        with self.lock:
            self.project = None
            self.web = WebMetadata()
            self.feeder_references = {}
            self.path = None
            self.read_only_source = False
            self.source_format = "NONE"
            self.dirty = False
            self.revision = 0
            self.calculation = None
            self.calculation_revision = None
            self.last_error = None
            return {"closed": True}

    def update_general(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            try:
                existing_client_id = project.metadata.client_id
                if payload.get("detach_client"):
                    target_client_id = None
                    snapshot = _client_snapshot(
                        payload.get("client", ""),
                        payload.get("address", ""),
                    )
                elif payload.get("client_id"):
                    target_client_id = str(payload["client_id"])
                    if (
                        target_client_id == existing_client_id
                        and not payload.get("refresh_client")
                        and project.client_snapshot is not None
                    ):
                        snapshot = project.client_snapshot
                    else:
                        snapshot = self._snapshot_for_client(
                            target_client_id,
                            payload.get("client", ""),
                            payload.get("address", ""),
                        )
                elif existing_client_id is not None:
                    target_client_id = existing_client_id
                    snapshot = project.client_snapshot
                else:
                    target_client_id = None
                    snapshot = _client_snapshot(
                        payload.get("client", ""),
                        payload.get("address", ""),
                    )
                metadata = project.metadata.changed(
                    code=payload["reference"],
                    designation=payload["name"],
                    author=payload.get("author", ""),
                    client_id=target_client_id,
                    revision=payload.get("revision", project.metadata.revision),
                    standard=payload.get("standard", project.metadata.standard),
                )
                self.project = project.with_metadata(metadata, snapshot)
                self.web = WebMetadata(
                    site=payload.get("site", ""),
                    address=payload.get("address", ""),
                    observations=payload.get("observations", ""),
                    created_by=payload.get("author", ""),
                )
                self._touch()
                return self._payload()
            except ProjectStoreError:
                raise
            except Exception as exc:
                raise _model_error(exc) from exc

    def add_board(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            try:
                parent_id = payload["parent_board_id"]
                parent = project.electrical.board_map().get(parent_id)
                if parent is None:
                    raise ProjectStoreError(
                        "TABLEAU_PARENT_INTROUVABLE", "Tableau parent introuvable.", 404
                    )
                board_id = payload.get("board_id") or _next_id(
                    "TD", set(project.electrical.board_map())
                )
                feeder_id = _next_id("DEP", set(project.electrical.feeder_map()))
                network = parent.network.value
                voltage = str(parent.voltage_v)
                board = Board(
                    board_id=board_id,
                    designation=payload["designation"],
                    board_type=BoardType.DIVISIONNAIRE,
                    network=network,
                    voltage_v=voltage,
                    parent_feeder_id=feeder_id,
                    description=payload.get("description", ""),
                    has_neutral=bool(payload.get("has_neutral", parent.has_neutral)),
                    voltage_ln_v=payload.get("voltage_ln_v"),
                )
                feeder = Feeder(
                    feeder_id=feeder_id,
                    designation=f"Alimentation {payload['designation']}",
                    parent_board_id=parent_id,
                    network=network,
                    voltage_v=voltage,
                    downstream_board_id=board_id,
                    description="Créé par WEB-03",
                    has_neutral=board.has_neutral,
                )
                self.project = replace(
                    project, electrical=project.electrical.add_board_with_feeder(board, feeder)
                )
                self._touch()
                return self._payload()
            except ProjectStoreError:
                raise
            except Exception as exc:
                raise _model_error(exc) from exc

    def update_board(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            try:
                board = project.electrical.board_map().get(payload["board_id"])
                if board is None:
                    raise ProjectStoreError("TABLEAU_INTROUVABLE", "Tableau introuvable.", 404)
                updated = replace(
                    board,
                    designation=payload.get("designation", board.designation),
                    description=payload.get("description", board.description),
                    has_neutral=bool(payload.get("has_neutral", board.has_neutral)),
                    voltage_ln_v=payload.get("voltage_ln_v"),
                )
                self.project = replace(
                    project, electrical=project.electrical.replace_board(updated)
                )
                self._touch()
                return self._payload()
            except ProjectStoreError:
                raise
            except Exception as exc:
                raise _model_error(exc) from exc

    def add_feeder(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            try:
                parent = project.electrical.board_map().get(payload["parent_board_id"])
                if parent is None:
                    raise ProjectStoreError(
                        "TABLEAU_PARENT_INTROUVABLE", "Tableau parent introuvable.", 404
                    )
                feeder_id = payload.get("feeder_id") or _next_id(
                    "DEP", set(project.electrical.feeder_map())
                )
                requested_reference = _normalized_reference(payload.get("reference"))
                if bool(payload.get("auto_reference")) or not requested_reference:
                    reference = _next_feeder_reference(
                        project.electrical,
                        payload["parent_board_id"],
                        self.feeder_references,
                    )
                else:
                    _check_feeder_reference(
                        project.electrical,
                        payload["parent_board_id"],
                        requested_reference,
                        self.feeder_references,
                    )
                    reference = requested_reference
                try:
                    distribution = resolve_distribution(parent, payload)
                except DistributionError as exc:
                    raise ProjectStoreError(exc.code, exc.message, 422) from exc
                feeder = Feeder(
                    feeder_id=feeder_id,
                    designation=payload["designation"],
                    parent_board_id=payload["parent_board_id"],
                    network=distribution["network"],
                    voltage_v=distribution["voltage_v"],
                    member_load_ids=(),
                    downstream_board_id=None,
                    ks=payload.get("ks") or None,
                    description=payload.get("description", ""),
                    phase=distribution["phase"],
                    voltage_ln_v=distribution["voltage_ln_v"],
                    has_neutral=distribution["has_neutral"],
                    draft=True,
                )
                self.project = replace(project, electrical=project.electrical.add_feeder(feeder))
                self.feeder_references[feeder_id] = reference
                self._touch()
                return self._payload()
            except ProjectStoreError:
                raise
            except Exception as exc:
                raise _model_error(exc) from exc

    def update_feeder(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            try:
                feeder = project.electrical.feeder_map().get(payload["feeder_id"])
                if feeder is None:
                    raise ProjectStoreError("DEPART_INTROUVABLE", "Départ introuvable.", 404)
                parent = project.electrical.board_map().get(feeder.parent_board_id)
                if parent is None:
                    raise ProjectStoreError(
                        "TABLEAU_PARENT_INTROUVABLE", "Tableau parent introuvable.", 404
                    )
                try:
                    distribution = resolve_distribution(parent, payload, existing=feeder)
                except DistributionError as exc:
                    raise ProjectStoreError(exc.code, exc.message, 422) from exc
                reference_supplied = bool(payload.get("auto_reference")) or payload.get(
                    "reference"
                ) is not None
                if reference_supplied:
                    if bool(payload.get("auto_reference")):
                        next_reference = _next_feeder_reference(
                            project.electrical,
                            feeder.parent_board_id,
                            self.feeder_references,
                            exclude_feeder_id=feeder.feeder_id,
                        )
                    else:
                        next_reference = _normalized_reference(payload.get("reference"))
                        _check_feeder_reference(
                            project.electrical,
                            feeder.parent_board_id,
                            next_reference,
                            self.feeder_references,
                            exclude_feeder_id=feeder.feeder_id,
                        )
                else:
                    next_reference = self.feeder_references.get(feeder.feeder_id, "")
                updated = replace(
                    feeder,
                    designation=payload.get("designation", feeder.designation),
                    description=payload.get("description", feeder.description),
                    ks=payload.get("ks") or None,
                    network=distribution["network"],
                    voltage_v=distribution["voltage_v"],
                    phase=distribution["phase"],
                    voltage_ln_v=distribution["voltage_ln_v"],
                    has_neutral=distribution["has_neutral"],
                )
                if updated.downstream_board_id is not None:
                    child = project.electrical.board_map().get(updated.downstream_board_id)
                    if child is None:
                        raise ProjectStoreError(
                            "TABLEAU_AVAL_INTROUVABLE", "Tableau aval introuvable.", 404
                        )
                    if (
                        updated.network_value is not child.network_value
                        or updated.voltage_value != child.voltage_v
                        or bool(updated.has_neutral) is not bool(child.has_neutral)
                    ):
                        raise ProjectStoreError(
                            "DISTRIBUTION_CHANGEMENT_INCOMPATIBLE",
                            "La distribution du départ ne correspond pas au tableau aval.",
                            422,
                        )
                electrical = project.electrical.replace_feeder(updated)
                if (
                    updated.network is Network.MONO
                    and updated.phase is not None
                    and updated.phase != feeder.phase
                ):
                    electrical = electrical.change_feeder_phase(
                        updated.feeder_id,
                        updated.phase,
                    )
                self.project = replace(project, electrical=electrical)
                if reference_supplied:
                    if next_reference:
                        self.feeder_references[feeder.feeder_id] = next_reference
                    else:
                        self.feeder_references.pop(feeder.feeder_id, None)
                self._touch()
                return self._payload()
            except ProjectStoreError:
                raise
            except Exception as exc:
                raise _model_error(exc) from exc

    def add_load(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            try:
                feeder = project.electrical.feeder_map().get(payload["feeder_id"])
                if feeder is None:
                    raise ProjectStoreError("DEPART_INTROUVABLE", "Départ introuvable.", 404)
                load_id = payload.get("load_id") or _next_id(
                    "REC", set(project.electrical.load_map())
                )
                load = Load(
                    load_id=load_id,
                    designation=payload["designation"],
                    network=payload.get("network", feeder.network.value),
                    voltage_v=payload.get("voltage_v", str(feeder.voltage_v)),
                    nominal_power=payload["nominal_power"],
                    power_unit=payload.get("power_unit", "W"),
                    quantity=payload.get("quantity", 1),
                    power_factor=payload.get("power_factor"),
                )
                parent = project.electrical.board_map().get(feeder.parent_board_id)
                phase = _phase_for_new_load(
                    feeder,
                    parent,
                    load.network.value,
                    payload.get("phase"),
                )
                assignment = LoadAssignment(
                    entry=LoadEntry(load=load, ku=payload.get("ku", "1")),
                    feeder_id=feeder.feeder_id,
                    phase=phase,
                )
                self.project = replace(project, electrical=project.electrical.add_load(assignment))
                self._touch()
                return self._payload()
            except ProjectStoreError:
                raise
            except Exception as exc:
                raise _model_error(exc) from exc

    def update_load(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            try:
                current = project.electrical.load_map().get(payload["load_id"])
                if current is None:
                    raise ProjectStoreError("CHARGE_INTROUVABLE", "Récepteur introuvable.", 404)
                feeder_id = payload.get("feeder_id") or current.feeder_id
                target_feeder = project.electrical.feeder_map().get(feeder_id)
                if target_feeder is None:
                    raise ProjectStoreError("DEPART_INTROUVABLE", "Départ introuvable.", 404)
                target_board = project.electrical.board_map().get(target_feeder.parent_board_id)
                load = Load(
                    load_id=current.entry.load_id,
                    designation=payload.get("designation", current.entry.load.designation),
                    network=payload.get("network") or current.entry.load.network.value,
                    voltage_v=payload.get("voltage_v", str(current.entry.load.voltage_v)),
                    nominal_power=payload.get(
                        "nominal_power", str(current.entry.load.nominal_power)
                    ),
                    power_unit=payload.get("power_unit", str(current.entry.load.power_unit)),
                    quantity=payload.get("quantity", current.entry.load.quantity),
                    power_factor=payload.get("power_factor", str(current.entry.load.power_factor)),
                )
                target_phase = _phase_for_updated_load(
                    target_feeder,
                    target_board,
                    load.network.value,
                    payload.get("phase"),
                    current.phase,
                )
                electrical = project.electrical
                if feeder_id != current.feeder_id:
                    electrical = electrical.move_load(current.entry.load_id, feeder_id)
                    current = electrical.load_map()[current.entry.load_id]
                    target_feeder = electrical.feeder_map()[feeder_id]
                if target_feeder.network is Network.MONO and target_phase != _phase_text(
                    target_feeder.phase
                ):
                    # The monophase supply owns its phase. Changing a load
                    # phase therefore moves the supply and every member load in
                    # one immutable candidate, not just this assignment.
                    electrical = electrical.change_feeder_phase(feeder_id, target_phase)
                    current = electrical.load_map()[current.entry.load_id]
                assignment = replace(
                    current,
                    entry=LoadEntry(load=load, ku=payload.get("ku", current.entry.ku)),
                    phase=target_phase,
                )
                self.project = replace(project, electrical=electrical.replace_load(assignment))
                self._touch()
                return self._payload()
            except ProjectStoreError:
                raise
            except Exception as exc:
                raise _model_error(exc) from exc

    def delete(self, kind: str, entity_id: str) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            try:
                electrical = project.electrical
                if kind == "board":
                    board = electrical.board_map().get(entity_id)
                    if board is None:
                        raise ProjectStoreError(
                            "TABLEAU_INTROUVABLE", "Tableau à supprimer introuvable.", 404
                        )
                    if board.parent_feeder_id is None or board.board_type is BoardType.TGBT:
                        raise ProjectStoreError(
                            "SUPPRESSION_RACINE_REFUSEE",
                            "Le TGBT racine ne peut pas être supprimé.",
                            422,
                        )
                    electrical = electrical.remove_board(entity_id)
                elif kind == "feeder":
                    electrical = electrical.remove_feeder(entity_id)
                elif kind == "load":
                    electrical = electrical.remove_load(entity_id)
                else:
                    raise ProjectStoreError(
                        "TYPE_SUPPRESSION_INVALIDE", "Type de suppression invalide.", 400
                    )
                self.project = replace(project, electrical=electrical)
                feeder_ids = set(electrical.feeder_map())
                self.feeder_references = {
                    feeder_id: reference
                    for feeder_id, reference in self.feeder_references.items()
                    if feeder_id in feeder_ids
                }
                self._touch()
                return self._payload()
            except ProjectStoreError:
                raise
            except Exception as exc:
                raise _model_error(exc) from exc

    def recalculate(self) -> dict[str, Any]:
        with self.lock:
            self._require_project()
            self._recalculate()
            return self._payload()

    def list_files(self) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        for base in (self.root, WORKTREE / "examples", WORKTREE / "fixtures"):
            if not base.exists():
                continue
            for path in sorted(base.glob("*.json")):
                if (
                    path.name.endswith(WEB_SUFFIX)
                    or path.name.endswith((".calcelect-v1.3.json", "-v1.3.json"))
                    or path.name.endswith((".calcelect-v1.4.json", "-v1.4.json"))
                ):
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    client_id: str | None = None
                    client_name = ""
                    if path.name.endswith(WEB_SUFFIX):
                        client_id, client_name = _web_client_info(path)
                    files.append(
                        {
                            "name": path.name,
                            "path": str(path),
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                            "writable": base == self.root,
                            "format": "WEB-03"
                            if path.name.endswith(WEB_SUFFIX)
                            else ("V1.4" if path.name.endswith(".calcelect-v1.4.json") else "V1.3"),
                            "client_id": client_id,
                            "client_name": client_name,
                        }
                    )
        return files

    def _resolve_read_path(self, path: Path) -> Path:
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise ProjectStoreError("PROJET_INTROUVABLE", "Fichier projet introuvable.", 404)
        if not any(_is_under(resolved, root) for root in self.read_roots):
            raise ProjectStoreError(
                "CHEMIN_NON_AUTORISE", "Lecture hors du périmètre autorisé.", 403
            )
        if resolved.stat().st_size > MAX_PROJECT_BYTES:
            raise ProjectStoreError(
                "PROJET_TROP_VOLUMINEUX", "Fichier projet trop volumineux.", 413
            )
        return resolved

    def _resolve_write_path(self, path: Path) -> Path:
        resolved = path.expanduser().resolve()
        if not _is_under(resolved, self.root):
            raise ProjectStoreError(
                "CHEMIN_NON_AUTORISE", "Écriture hors du répertoire de qualification.", 403
            )
        if not resolved.name.endswith(WEB_SUFFIX):
            raise ProjectStoreError(
                "EXTENSION_NON_AUTORISEE", f"L'extension doit être {WEB_SUFFIX}.", 415
            )
        if resolved.is_symlink():
            raise ProjectStoreError(
                "LIEN_SYMBOLIQUE_REFUSE", "Les liens symboliques sont refusés.", 403
            )
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def _atomic_write(self, path: Path, data: bytes, *, overwrite: bool) -> None:
        if len(data) > MAX_PROJECT_BYTES:
            raise ProjectStoreError(
                "PROJET_TROP_VOLUMINEUX", "Projet sérialisé trop volumineux.", 413
            )
        if path.exists() and not overwrite:
            raise ProjectStoreError(
                "FICHIER_EXISTE", "Le fichier existe déjà ; utiliser Enregistrer sous.", 409
            )
        previous = path.read_bytes() if path.exists() else None
        fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if previous is not None:
                backup_fd, backup_name = tempfile.mkstemp(
                    dir=path.parent, prefix=f".{path.name}.bak.", suffix=".tmp"
                )
                with os.fdopen(backup_fd, "wb") as backup_handle:
                    backup_handle.write(previous)
                    backup_handle.flush()
                    os.fsync(backup_handle.fileno())
                os.replace(backup_name, path.with_name(path.name + ".bak"))
            os.replace(temp, path)
            check = deserialize_web_project(path.read_bytes())
            if check[0].project_id != self._require_project().project_id:
                raise ProjectStoreError(
                    "VERIFICATION_ECHEC", "Le projet relu ne correspond pas.", 500
                )
        except Exception:
            if previous is not None and path.exists():
                restore_fd, restore_name = tempfile.mkstemp(
                    dir=path.parent, prefix=f".{path.name}.restore.", suffix=".tmp"
                )
                with os.fdopen(restore_fd, "wb") as restore_handle:
                    restore_handle.write(previous)
                    restore_handle.flush()
                    os.fsync(restore_handle.fileno())
                os.replace(restore_name, path)
            raise
        finally:
            if temp.exists():
                temp.unlink(missing_ok=True)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
