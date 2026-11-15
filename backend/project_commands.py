"""Transactional WEB-04 command layer over the existing WEB-03 store.

The electrical model remains ProjectV14 / ProjectV11. Commands are prepared on
immutable copies, recalculated by the existing Python engine, then published
with an incrementing revision. Undo/redo restore validated snapshots and never
publish a failed candidate.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from calcelect.hierarchy import Board, BoardType, Feeder, LoadAssignment, ProjectV11
from calcelect.models import LoadEntry
from calcelect.service_v13 import calculate_project_v13
from calcelect.validation import utc_now
from segyr_calc.a2.models import Load
from segyr_calc.core.power import Network

from .project_store import (
    ProjectStore,
    ProjectStoreError,
    WebMetadata,
    _next_id,
    serialize_web_project,
)

HISTORY_LIMIT = 50


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    project: Any
    web: WebMetadata
    feeder_references: dict[str, str]
    label: str
    revision: int
    calculation_revision: int | None
    calculation: Any | None
    last_error: str | None


def _fingerprint(
    project: Any,
    web: WebMetadata,
    feeder_references: dict[str, str] | None = None,
) -> str:
    return hashlib.sha256(
        serialize_web_project(project, web, feeder_references or {})
    ).hexdigest()


def _descendant_board_ids(electrical: ProjectV11, board_id: str) -> list[str]:
    result: list[str] = []
    stack = [board_id]
    seen = {board_id}
    while stack:
        current = stack.pop()
        for feeder in electrical.feeders_of(current):
            child = feeder.downstream_board_id
            if child is not None and child not in seen:
                seen.add(child)
                result.append(child)
                stack.append(child)
    return result


def _subtree_feeders(electrical: ProjectV11, board_ids: set[str]) -> list[Feeder]:
    return [feeder for feeder in electrical.feeders if feeder.parent_board_id in board_ids]


def _subtree_load_ids(feeders: list[Feeder]) -> list[str]:
    result: list[str] = []
    for feeder in feeders:
        result.extend(feeder.member_load_ids)
    return result


def _copy_load(load: Load, new_id: str, suffix: str) -> Load:
    return Load(
        load_id=new_id,
        designation=f"{load.designation}{suffix}",
        network=load.network.value,
        voltage_v=str(load.voltage_v),
        nominal_power=str(load.nominal_power),
        power_unit=load.power_unit.value,
        quantity=load.quantity,
        power_factor=str(load.power_factor),
    )


def _copied_feeder_id(electrical: ProjectV11) -> str:
    return _next_id("DEP", set(electrical.feeder_map()))


def _copied_board_id(electrical: ProjectV11) -> str:
    return _next_id("TD", set(electrical.board_map()))


def _copied_load_id(electrical: ProjectV11) -> str:
    return _next_id("REC", set(electrical.load_map()))


def _duplicate_terminal_feeder(
    electrical: ProjectV11,
    feeder: Feeder,
    destination_board_id: str,
    *,
    suffix: str = " (copie)",
) -> ProjectV11:
    if feeder.downstream_board_id is not None:
        raise ProjectStoreError(
            "DEPART_TABLEAU_NON_DUPLICABLE",
            "Un départ d'alimentation de tableau doit être dupliqué avec son tableau.",
            422,
        )
    new_feeder_id = _copied_feeder_id(electrical)
    copied_feeder = Feeder(
        feeder_id=new_feeder_id,
        designation=f"{feeder.designation}{suffix}",
        parent_board_id=destination_board_id,
        network=feeder.network.value,
        voltage_v=str(feeder.voltage_v),
        member_load_ids=(),
        downstream_board_id=None,
        ks=str(feeder.ks) if feeder.ks is not None else None,
        description=feeder.description,
        phase=feeder.phase.value if feeder.phase is not None else None,
        voltage_ln_v=str(feeder.voltage_ln_v) if feeder.voltage_ln_v is not None else None,
        has_neutral=feeder.has_neutral,
        draft=True,
    )
    result = electrical.add_feeder(copied_feeder)
    for load_id in feeder.member_load_ids:
        assignment = result.load_map().get(load_id)
        if assignment is None:
            continue
        new_load_id = _copied_load_id(result)
        new_load = _copy_load(assignment.entry.load, new_load_id, suffix)
        target_phase = (
            copied_feeder.phase
            if copied_feeder.network is Network.MONO and copied_feeder.phase is not None
            else assignment.phase
        )
        new_assignment = LoadAssignment(
            entry=LoadEntry(load=new_load, ku=str(assignment.entry.ku)),
            feeder_id=new_feeder_id,
            phase=target_phase,
        )
        result = result.add_load(new_assignment)
    return result


def _duplicate_board_subtree(
    electrical: ProjectV11,
    board_id: str,
    destination_board_id: str,
    *,
    suffix: str = " (copie)",
) -> ProjectV11:
    original = electrical.board_map().get(board_id)
    destination = electrical.board_map().get(destination_board_id)
    if original is None:
        raise ProjectStoreError("TABLEAU_INTROUVABLE", "Tableau à dupliquer introuvable.", 404)
    if destination is None:
        raise ProjectStoreError("TABLEAU_DESTINATION_INTROUVABLE", "Destination introuvable.", 404)
    if original.board_type is BoardType.TGBT:
        raise ProjectStoreError(
            "DUPLICATION_RACINE_REFUSEE",
            "Le TGBT racine ne peut pas être dupliqué par cette commande.",
            422,
        )
    if (
        destination.network is not original.network
        or destination.voltage_value != original.voltage_value
    ):
        raise ProjectStoreError(
            "TABLEAU_INCOMPATIBLE",
            "Réseau ou tension incompatibles avec la destination.",
            422,
        )

    new_board_id = _copied_board_id(electrical)
    new_feeder_id = _copied_feeder_id(electrical)
    copied_board = Board(
        board_id=new_board_id,
        designation=f"{original.designation}{suffix}",
        board_type=original.board_type,
        network=original.network.value,
        voltage_v=str(original.voltage_v),
        parent_feeder_id=new_feeder_id,
        description=original.description,
        phases_available=original.phases_available,
        has_neutral=original.has_neutral,
        voltage_ln_v=str(original.voltage_ln_v) if original.voltage_ln_v is not None else None,
    )
    copied_feeder = Feeder(
        feeder_id=new_feeder_id,
        designation=f"Alimentation {copied_board.designation}",
        parent_board_id=destination_board_id,
        network=original.network.value,
        voltage_v=str(original.voltage_v),
        downstream_board_id=new_board_id,
        description=f"Copie de {original.designation}",
        has_neutral=original.has_neutral,
    )
    result = electrical.add_board_with_feeder(copied_board, copied_feeder)

    for outgoing in electrical.feeders_of(board_id):
        if outgoing.downstream_board_id is not None:
            result = _duplicate_board_subtree(
                result,
                outgoing.downstream_board_id,
                new_board_id,
                suffix=suffix,
            )
        else:
            result = _duplicate_terminal_feeder(
                result,
                outgoing,
                new_board_id,
                suffix=suffix,
            )
    return result


class CommandProjectStore(ProjectStore):
    def __init__(self, root=None, read_roots=None, client_store=None) -> None:
        super().__init__(root=root, read_roots=read_roots, client_store=client_store)
        self.undo_stack: list[HistoryEntry] = []
        self.redo_stack: list[HistoryEntry] = []
        self.last_command_label = "Projet initial"
        self.saved_fingerprint: str | None = None
        self.fingerprint: str | None = None

    @property
    def state(self) -> dict[str, Any]:
        base: Any = super().state
        base.update(
            {
                "can_undo": bool(self.undo_stack),
                "can_redo": bool(self.redo_stack),
                "undo_label": self.last_command_label if self.undo_stack else None,
                "redo_label": self.redo_stack[-1].label if self.redo_stack else None,
                "history_length": len(self.undo_stack) + len(self.redo_stack),
                "undo_depth": len(self.undo_stack),
                "redo_depth": len(self.redo_stack),
                "history_limit": HISTORY_LIMIT,
            }
        )
        return base

    def _snapshot(self) -> HistoryEntry:
        return HistoryEntry(
            project=self.project,
            web=self.web,
            feeder_references=dict(self.feeder_references),
            label=self.last_command_label,
            revision=self.revision,
            calculation_revision=self.calculation_revision,
            calculation=self.calculation,
            last_error=self.last_error,
        )

    def _restore(self, entry: HistoryEntry) -> None:
        self.project = entry.project
        self.web = entry.web
        self.feeder_references = dict(entry.feeder_references)
        self.last_command_label = entry.label
        self.revision = entry.revision
        self.calculation_revision = entry.calculation_revision
        self.calculation = entry.calculation
        self.last_error = entry.last_error
        self._update_dirty()

    def _push_undo(self, entry: HistoryEntry) -> None:
        self.undo_stack.append(entry)
        if len(self.undo_stack) > HISTORY_LIMIT:
            del self.undo_stack[: len(self.undo_stack) - HISTORY_LIMIT]

    def _update_dirty(self) -> None:
        if self.project is None:
            self.fingerprint = None
            self.dirty = False
            return
        self.fingerprint = _fingerprint(self.project, self.web, self.feeder_references)
        self.dirty = self.saved_fingerprint is None or self.fingerprint != self.saved_fingerprint

    def _check_revision(self, expected_revision: int | None) -> None:
        if expected_revision is not None and expected_revision != self.revision:
            raise ProjectStoreError(
                "REVISION_OBSOLETE",
                "La révision du projet a changé ; rechargez l'état courant.",
                409,
            )

    def _reset_history(self, label: str) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.last_command_label = label

    def _wrap(
        self,
        label: str,
        expected_revision: int | None,
        operation: Callable[[], Any],
    ) -> dict[str, Any]:
        with self.lock:
            self._require_project()
            self._check_revision(expected_revision)
            before = self._snapshot()
            self.last_error = None
            try:
                operation()
            except Exception:
                self._restore(before)
                raise
            if self.last_error is not None or self.calculation is None:
                message = self.last_error or "Le moteur n'a pas produit de résultat."
                self._restore(before)
                raise ProjectStoreError("CALCUL_ECHEC", message, 422)
            self._push_undo(before)
            self.last_command_label = label
            self.redo_stack.clear()
            self._update_dirty()
            return self._payload()

    def _commit_candidate(
        self,
        label: str,
        expected_revision: int | None,
        candidate: Any,
        web: WebMetadata | None = None,
        feeder_references: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        with self.lock:
            self._require_project()
            self._check_revision(expected_revision)
            candidate_web = web or self.web
            before = self._snapshot()
            try:
                calculation = calculate_project_v13(candidate.electrical)
            except Exception as exc:
                raise ProjectStoreError("CALCUL_ECHEC", f"Recalcul refusé: {exc}", 422) from exc
            self.project = candidate
            self.web = candidate_web
            if feeder_references is not None:
                self.feeder_references = dict(feeder_references)
            self.calculation = calculation
            self.revision = before.revision + 1
            self.calculation_revision = self.revision
            self.last_error = None
            self._push_undo(before)
            self.last_command_label = label
            self.redo_stack.clear()
            self._update_dirty()
            return self._payload()

    def new(self, **kwargs: Any) -> dict[str, Any]:
        payload = super().new(**kwargs)
        self._reset_history("Création du projet")
        self.saved_fingerprint = None
        self._update_dirty()
        return payload

    def open(self, path) -> dict[str, Any]:
        payload = super().open(path)
        self._reset_history("Ouverture du projet")
        self.saved_fingerprint = _fingerprint(
            self.project, self.web, self.feeder_references
        )
        self._update_dirty()
        return payload

    def save(self, path=None, *, overwrite=False) -> dict[str, Any]:
        super().save(path, overwrite=overwrite)
        self.saved_fingerprint = _fingerprint(
            self.project, self.web, self.feeder_references
        )
        self._update_dirty()
        return self._payload()

    def save_as(self, path, *, overwrite=False) -> dict[str, Any]:
        return self.save(path, overwrite=overwrite)

    def duplicate(self, path, *, overwrite=False) -> dict[str, Any]:
        super().duplicate(path, overwrite=overwrite)
        self._reset_history("Duplication du projet")
        self.saved_fingerprint = _fingerprint(
            self.project, self.web, self.feeder_references
        )
        self._update_dirty()
        return self._payload()

    def close(self) -> dict[str, Any]:
        result = super().close()
        self._reset_history("Aucun projet")
        self.saved_fingerprint = None
        self.fingerprint = None
        self.dirty = False
        return result

    def update_general(self, payload: dict[str, Any]) -> dict[str, Any]:
        base: Any = super()
        return self._wrap(
            "Modification des informations générales",
            payload.get("expected_revision"),
            lambda: base.update_general(payload),
        )


    def update_source(self, payload: dict[str, Any]) -> dict[str, Any]:
        base: Any = super()
        label = (
            "Suppression de la source électrique"
            if payload.get("source") is None
            else "Modification de la source électrique"
        )
        return self._wrap(
            label,
            payload.get("expected_revision"),
            lambda: base.update_source(payload),
        )

    def add_board(self, payload: dict[str, Any]) -> dict[str, Any]:
        base: Any = super()
        return self._wrap(
            "Création d'un tableau",
            payload.get("expected_revision"),
            lambda: base.add_board(payload),
        )

    def update_board(self, payload: dict[str, Any]) -> dict[str, Any]:
        base: Any = super()
        return self._wrap(
            "Modification d'un tableau",
            payload.get("expected_revision"),
            lambda: base.update_board(payload),
        )

    def add_feeder(self, payload: dict[str, Any]) -> dict[str, Any]:
        base: Any = super()
        return self._wrap(
            "Création d'un départ",
            payload.get("expected_revision"),
            lambda: base.add_feeder(payload),
        )

    def update_feeder(self, payload: dict[str, Any]) -> dict[str, Any]:
        base: Any = super()
        return self._wrap(
            "Modification d'un départ",
            payload.get("expected_revision"),
            lambda: base.update_feeder(payload),
        )

    def add_feeder_with_load(self, payload: dict[str, Any]) -> dict[str, Any]:
        expected_revision = payload.get("expected_revision")

        with self.lock:
            project = self._require_project()
            self._check_revision(expected_revision)
            before = set(project.electrical.feeder_map())

            # Prepare and validate both elements in an isolated working store.
            # The real project is not mutated until the whole candidate has
            # been accepted by the existing calculation engine.
            candidate = ProjectStore(
                root=self.root,
                read_roots=self.read_roots,
                client_store=self.client_store,
            )
            candidate.project = project
            candidate.web = self.web
            candidate.feeder_references = dict(self.feeder_references)
            candidate.path = self.path
            candidate.read_only_source = self.read_only_source
            candidate.source_format = self.source_format
            candidate.dirty = self.dirty
            candidate.revision = self.revision
            candidate.calculation_revision = self.calculation_revision
            candidate.calculation = self.calculation
            candidate.last_error = self.last_error

            feeder_payload = dict(payload["feeder"])
            feeder_payload["parent_board_id"] = payload["parent_board_id"]
            candidate.add_feeder(feeder_payload)
            created = [
                feeder
                for feeder in candidate._require_project().electrical.feeders
                if feeder.feeder_id not in before
            ]
            if len(created) != 1:
                raise ProjectStoreError(
                    "CREATION_DEPART_ECHEC",
                    "Le départ créé n'a pas pu être identifié.",
                    500,
                )
            load_payload = dict(payload["load"])
            load_payload["feeder_id"] = created[0].feeder_id
            candidate.add_load(load_payload)
            candidate_project = candidate._require_project()

            return self._commit_candidate(
                "Création d'un départ et de son premier récepteur",
                expected_revision,
                candidate_project,
                web=candidate.web,
                feeder_references=candidate.feeder_references,
            )

    def add_load(self, payload: dict[str, Any]) -> dict[str, Any]:
        base: Any = super()
        return self._wrap(
            "Création d'un récepteur",
            payload.get("expected_revision"),
            lambda: base.add_load(payload),
        )

    def update_load(self, payload: dict[str, Any]) -> dict[str, Any]:
        base: Any = super()
        return self._wrap(
            "Modification d'un récepteur",
            payload.get("expected_revision"),
            lambda: base.update_load(payload),
        )

    def move_board(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            electrical = project.electrical
            board_id = payload["board_id"]
            destination_id = payload["destination_board_id"]
            board = electrical.board_map().get(board_id)
            destination = electrical.board_map().get(destination_id)
            if board is None:
                raise ProjectStoreError("TABLEAU_INTROUVABLE", "Tableau introuvable.", 404)
            if destination is None:
                raise ProjectStoreError(
                    "TABLEAU_DESTINATION_INTROUVABLE", "Destination introuvable.", 404
                )
            if board.parent_feeder_id is None or board.board_type is BoardType.TGBT:
                raise ProjectStoreError(
                    "DEPLACEMENT_RACINE_REFUSE", "Le TGBT racine ne peut pas être déplacé.", 422
                )
            if destination_id == board_id or destination_id in _descendant_board_ids(
                electrical, board_id
            ):
                raise ProjectStoreError(
                    "CYCLE_INTERDIT", "Un tableau ne peut pas être déplacé sous lui-même.", 422
                )
            if (
                destination.network is not board.network
                or destination.voltage_value != board.voltage_value
            ):
                raise ProjectStoreError(
                    "TABLEAU_INCOMPATIBLE",
                    "Réseau ou tension incompatibles avec la destination.",
                    422,
                )
            old_feeder = electrical.feeder_map().get(board.parent_feeder_id)
            if old_feeder is None or old_feeder.downstream_board_id != board_id:
                raise ProjectStoreError(
                    "HIERARCHIE_INCOHERENTE", "Départ parent du tableau incohérent.", 422
                )
            if old_feeder.parent_board_id == destination_id:
                return self._payload()
            new_feeder_id = _next_id("DEP", set(electrical.feeder_map()))
            new_feeder = Feeder(
                feeder_id=new_feeder_id,
                designation=old_feeder.designation,
                parent_board_id=destination_id,
                network=board.network.value,
                voltage_v=str(board.voltage_v),
                downstream_board_id=board_id,
                description=old_feeder.description,
                has_neutral=old_feeder.has_neutral,
            )
            candidate_electrical = replace(
                electrical,
                boards=tuple(
                    replace(item, parent_feeder_id=new_feeder_id)
                    if item.board_id == board_id
                    else item
                    for item in electrical.boards
                ),
                feeders=(
                    *tuple(
                        item
                        for item in electrical.feeders
                        if item.feeder_id != old_feeder.feeder_id
                    ),
                    new_feeder,
                ),
                updated_at=utc_now(),
            )
            candidate = replace(project, electrical=candidate_electrical)
            return self._commit_candidate(
                "Déplacement d'un tableau",
                payload.get("expected_revision"),
                candidate,
            )

    def duplicate_board(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            electrical = project.electrical
            board_id = payload["board_id"]
            board = electrical.board_map().get(board_id)
            if board is None:
                raise ProjectStoreError("TABLEAU_INTROUVABLE", "Tableau introuvable.", 404)
            if board.parent_feeder_id is None:
                raise ProjectStoreError(
                    "DUPLICATION_RACINE_REFUSEE", "Le TGBT racine ne peut pas être dupliqué.", 422
                )
            parent_feeder = electrical.feeder_map().get(board.parent_feeder_id)
            default_destination = parent_feeder.parent_board_id if parent_feeder else None
            destination_id = payload.get("destination_board_id") or default_destination
            if not destination_id:
                raise ProjectStoreError(
                    "TABLEAU_DESTINATION_INTROUVABLE", "Destination introuvable.", 404
                )
            if destination_id == board_id or destination_id in _descendant_board_ids(
                electrical, board_id
            ):
                raise ProjectStoreError(
                    "CYCLE_INTERDIT", "Un tableau ne peut pas être dupliqué sous lui-même.", 422
                )
            candidate_electrical = _duplicate_board_subtree(electrical, board_id, destination_id)
            candidate = replace(project, electrical=candidate_electrical)
            return self._commit_candidate(
                "Duplication d'un tableau",
                payload.get("expected_revision"),
                candidate,
            )

    def move_feeder(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            electrical = project.electrical
            feeder = electrical.feeder_map().get(payload["feeder_id"])
            destination = electrical.board_map().get(payload["destination_board_id"])
            if feeder is None:
                raise ProjectStoreError("DEPART_INTROUVABLE", "Départ introuvable.", 404)
            if destination is None:
                raise ProjectStoreError(
                    "TABLEAU_DESTINATION_INTROUVABLE", "Destination introuvable.", 404
                )
            if feeder.downstream_board_id is not None:
                raise ProjectStoreError(
                    "DEPART_TABLEAU_NON_DEPLACABLE",
                    "Déplacez le tableau aval, pas son départ d'alimentation.",
                    422,
                )
            if (
                destination.network is not feeder.network
                or destination.voltage_value != feeder.voltage_value
            ):
                raise ProjectStoreError(
                    "DEPART_INCOMPATIBLE",
                    "Réseau ou tension incompatibles avec la destination.",
                    422,
                )
            if feeder.parent_board_id == destination.board_id:
                return self._payload()
            load_ids = tuple(feeder.member_load_ids)
            new_feeder = replace(
                feeder,
                parent_board_id=destination.board_id,
                member_load_ids=load_ids,
                draft=not load_ids,
            )
            candidate_electrical = replace(
                electrical,
                feeders=tuple(
                    new_feeder if item.feeder_id == feeder.feeder_id else item
                    for item in electrical.feeders
                ),
                updated_at=utc_now(),
            )
            candidate = replace(project, electrical=candidate_electrical)
            return self._commit_candidate(
                "Déplacement d'un départ",
                payload.get("expected_revision"),
                candidate,
            )

    def duplicate_feeder(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            electrical = project.electrical
            feeder = electrical.feeder_map().get(payload["feeder_id"])
            if feeder is None:
                raise ProjectStoreError("DEPART_INTROUVABLE", "Départ introuvable.", 404)
            destination_id = payload.get("destination_board_id") or feeder.parent_board_id
            destination = electrical.board_map().get(destination_id)
            if destination is None:
                raise ProjectStoreError(
                    "TABLEAU_DESTINATION_INTROUVABLE", "Destination introuvable.", 404
                )
            if (
                destination.network is not feeder.network
                or destination.voltage_value != feeder.voltage_value
            ):
                raise ProjectStoreError(
                    "DEPART_INCOMPATIBLE",
                    "Réseau ou tension incompatibles avec la destination.",
                    422,
                )
            candidate_electrical = _duplicate_terminal_feeder(electrical, feeder, destination_id)
            candidate = replace(project, electrical=candidate_electrical)
            return self._commit_candidate(
                "Duplication d'un départ",
                payload.get("expected_revision"),
                candidate,
            )

    def move_load(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            electrical = project.electrical
            assignment = electrical.load_map().get(payload["load_id"])
            if assignment is None:
                raise ProjectStoreError("CHARGE_INTROUVABLE", "Récepteur introuvable.", 404)
            destination = electrical.feeder_map().get(payload["destination_feeder_id"])
            if destination is None:
                raise ProjectStoreError(
                    "DEPART_INTROUVABLE", "Départ destination introuvable.", 404
                )
            if destination.downstream_board_id is not None:
                raise ProjectStoreError(
                    "DEPART_INCOMPATIBLE",
                    "Un départ tableau ne peut pas recevoir de récepteur.",
                    422,
                )
            candidate_electrical = electrical.move_load(
                assignment.entry.load_id, destination.feeder_id
            )
            candidate = replace(project, electrical=candidate_electrical)
            return self._commit_candidate(
                "Déplacement d'un récepteur",
                payload.get("expected_revision"),
                candidate,
            )

    def duplicate_load(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            electrical = project.electrical
            assignment = electrical.load_map().get(payload["load_id"])
            if assignment is None:
                raise ProjectStoreError("CHARGE_INTROUVABLE", "Récepteur introuvable.", 404)
            destination_id = payload.get("destination_feeder_id") or assignment.feeder_id
            destination = electrical.feeder_map().get(destination_id) if destination_id else None
            if destination is None:
                raise ProjectStoreError(
                    "DEPART_INTROUVABLE", "Départ destination introuvable.", 404
                )
            if destination.downstream_board_id is not None:
                raise ProjectStoreError(
                    "DEPART_INCOMPATIBLE",
                    "Un départ tableau ne peut pas recevoir de récepteur.",
                    422,
                )
            new_load_id = _next_id("REC", set(electrical.load_map()))
            new_load = _copy_load(assignment.entry.load, new_load_id, " (copie)")
            target_phase = (
                destination.phase
                if destination.network is Network.MONO and destination.phase is not None
                else assignment.phase
            )
            new_assignment = LoadAssignment(
                entry=LoadEntry(load=new_load, ku=str(assignment.entry.ku)),
                feeder_id=destination.feeder_id,
                phase=target_phase,
            )
            candidate_electrical = electrical.add_load(new_assignment)
            candidate = replace(project, electrical=candidate_electrical)
            return self._commit_candidate(
                "Duplication d'un récepteur",
                payload.get("expected_revision"),
                candidate,
            )

    def delete(
        self,
        kind: str,
        entity_id: str,
        *,
        cascade: bool = False,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        labels = {
            "board": "Suppression d'un tableau",
            "feeder": "Suppression d'un départ",
            "load": "Suppression d'un récepteur",
        }
        if not cascade:
            base: Any = super()
            return self._wrap(
                labels.get(kind, "Suppression"),
                expected_revision,
                lambda: base.delete(kind, entity_id),
            )
        with self.lock:
            project = self._require_project()
            electrical = project.electrical
            if kind == "board":
                board = electrical.board_map().get(entity_id)
                if board is None:
                    raise ProjectStoreError("TABLEAU_INTROUVABLE", "Tableau introuvable.", 404)
                if board.parent_feeder_id is None or board.board_type is BoardType.TGBT:
                    raise ProjectStoreError(
                        "SUPPRESSION_RACINE_REFUSEE",
                        "Le TGBT racine ne peut pas être supprimé.",
                        422,
                    )
                candidate_electrical = self._delete_board_cascade(electrical, entity_id)
            elif kind == "feeder":
                candidate_electrical = self._delete_feeder_cascade(electrical, entity_id)
            elif kind == "load":
                candidate_electrical = electrical.remove_load(entity_id)
            else:
                raise ProjectStoreError(
                    "TYPE_SUPPRESSION_INVALIDE", "Type de suppression invalide.", 400
                )
            candidate = replace(project, electrical=candidate_electrical)
            return self._commit_candidate(
                labels.get(kind, "Suppression"),
                expected_revision,
                candidate,
            )

    def _delete_board_cascade(self, electrical: ProjectV11, board_id: str) -> ProjectV11:
        board_ids = {board_id, *_descendant_board_ids(electrical, board_id)}
        feeders = _subtree_feeders(electrical, board_ids)
        board = electrical.board_map()[board_id]
        feeder_ids = {feeder.feeder_id for feeder in feeders}
        if board.parent_feeder_id is not None:
            feeder_ids.add(board.parent_feeder_id)
        load_ids = set(_subtree_load_ids(feeders))
        return replace(
            electrical,
            boards=tuple(item for item in electrical.boards if item.board_id not in board_ids),
            feeders=tuple(item for item in electrical.feeders if item.feeder_id not in feeder_ids),
            loads=tuple(item for item in electrical.loads if item.entry.load_id not in load_ids),
            updated_at=utc_now(),
        )

    def _delete_feeder_cascade(self, electrical: ProjectV11, feeder_id: str) -> ProjectV11:
        feeder = electrical.feeder_map().get(feeder_id)
        if feeder is None:
            raise ProjectStoreError("DEPART_INTROUVABLE", "Départ introuvable.", 404)
        board_ids: set[str] = set()
        feeder_ids: set[str] = {feeder_id}
        load_ids: set[str] = set(feeder.member_load_ids)
        if feeder.downstream_board_id is not None:
            board_ids = {
                feeder.downstream_board_id,
                *_descendant_board_ids(electrical, feeder.downstream_board_id),
            }
            child_feeders = _subtree_feeders(electrical, board_ids)
            feeder_ids.update(item.feeder_id for item in child_feeders)
            load_ids.update(_subtree_load_ids(child_feeders))
        return replace(
            electrical,
            boards=tuple(item for item in electrical.boards if item.board_id not in board_ids),
            feeders=tuple(item for item in electrical.feeders if item.feeder_id not in feeder_ids),
            loads=tuple(item for item in electrical.loads if item.entry.load_id not in load_ids),
            updated_at=utc_now(),
        )

    def delete_preview(self, kind: str, entity_id: str) -> dict[str, Any]:
        with self.lock:
            project = self._require_project()
            electrical = project.electrical
            if kind == "board":
                board = electrical.board_map().get(entity_id)
                if board is None:
                    raise ProjectStoreError("TABLEAU_INTROUVABLE", "Tableau introuvable.", 404)
                board_ids = {entity_id, *_descendant_board_ids(electrical, entity_id)}
                feeders = _subtree_feeders(electrical, board_ids)
                feeder_count = len(feeders) + (1 if board.parent_feeder_id is not None else 0)
                return {
                    "kind": kind,
                    "id": entity_id,
                    "designation": board.designation,
                    "boards": len(board_ids),
                    "feeders": feeder_count,
                    "loads": len(_subtree_load_ids(feeders)),
                    "descendants": [
                        electrical.board_map()[item].designation for item in sorted(board_ids)
                    ],
                    "root": board.parent_feeder_id is None or board.board_type is BoardType.TGBT,
                }
            if kind == "feeder":
                feeder = electrical.feeder_map().get(entity_id)
                if feeder is None:
                    raise ProjectStoreError("DEPART_INTROUVABLE", "Départ introuvable.", 404)
                board_ids = set()
                if feeder.downstream_board_id is not None:
                    board_ids = {
                        feeder.downstream_board_id,
                        *_descendant_board_ids(electrical, feeder.downstream_board_id),
                    }
                feeders = [feeder, *_subtree_feeders(electrical, board_ids)]
                return {
                    "kind": kind,
                    "id": entity_id,
                    "designation": feeder.designation,
                    "boards": len(board_ids),
                    "feeders": len(feeders),
                    "loads": len(_subtree_load_ids(feeders)),
                    "descendants": [
                        electrical.board_map()[item].designation for item in sorted(board_ids)
                    ],
                    "root": False,
                }
            if kind == "load":
                assignment = electrical.load_map().get(entity_id)
                if assignment is None:
                    raise ProjectStoreError("CHARGE_INTROUVABLE", "Récepteur introuvable.", 404)
                return {
                    "kind": kind,
                    "id": entity_id,
                    "designation": assignment.entry.load.designation,
                    "boards": 0,
                    "feeders": 0,
                    "loads": 1,
                    "descendants": [],
                    "root": False,
                }
            raise ProjectStoreError(
                "TYPE_SUPPRESSION_INVALIDE", "Type de suppression invalide.", 400
            )

    def undo(self, expected_revision: int | None = None) -> dict[str, Any]:
        with self.lock:
            self._require_project()
            self._check_revision(expected_revision)
            if not self.undo_stack:
                raise ProjectStoreError("AUCUNE_ANNULATION", "Aucune commande à annuler.", 409)
            entry = self.undo_stack[-1]
            try:
                calculation = calculate_project_v13(entry.project.electrical)
            except Exception as exc:
                raise ProjectStoreError("CALCUL_ECHEC", f"Annulation refusée: {exc}", 422) from exc
            current = self._snapshot()
            self.undo_stack.pop()
            self.redo_stack.append(current)
            self.project = entry.project
            self.web = entry.web
            self.feeder_references = dict(entry.feeder_references)
            self.last_command_label = entry.label
            self.revision = current.revision + 1
            self.calculation = calculation
            self.calculation_revision = self.revision
            self.last_error = None
            self._update_dirty()
            return self._payload()

    def redo(self, expected_revision: int | None = None) -> dict[str, Any]:
        with self.lock:
            self._require_project()
            self._check_revision(expected_revision)
            if not self.redo_stack:
                raise ProjectStoreError("AUCUN_RETABLISSEMENT", "Aucune commande à rétablir.", 409)
            entry = self.redo_stack[-1]
            try:
                calculation = calculate_project_v13(entry.project.electrical)
            except Exception as exc:
                raise ProjectStoreError(
                    "CALCUL_ECHEC", f"Rétablissement refusé: {exc}", 422
                ) from exc
            current = self._snapshot()
            self.redo_stack.pop()
            self.undo_stack.append(current)
            if len(self.undo_stack) > HISTORY_LIMIT:
                del self.undo_stack[: len(self.undo_stack) - HISTORY_LIMIT]
            self.project = entry.project
            self.web = entry.web
            self.feeder_references = dict(entry.feeder_references)
            self.last_command_label = entry.label
            self.revision = current.revision + 1
            self.calculation = calculation
            self.calculation_revision = self.revision
            self.last_error = None
            self._update_dirty()
            return self._payload()

    def recalculate(self) -> dict[str, Any]:
        return super().recalculate()
