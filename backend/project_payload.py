"""JSON payload composition for WEB-03 projects.

The electrical values come from the qualified engine. This module only maps
dataclasses and Decimal values for the local UI.
"""

from __future__ import annotations

from typing import Any

from .engine_adapter import (
    ASSUMPTIONS,
    PROJECT_SOURCE_SHA256,
    _board_payload,
    _diagnostics,
    _enum_text,
    _feeder_payload,
    _individual_load_results,
    _load_payload,
    _phase_triplet,
    _text,
)


def build_project_payload(
    project: Any,
    result: Any | None,
    *,
    web: dict[str, Any],
    state: dict[str, Any],
    data_class: str = "WEB03_PROJECT",
    client_id: str | None = None,
    client_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    feeder_map = {feeder.feeder_id: feeder for feeder in project.feeders}
    load_payloads: list[dict[str, Any]] = []
    boards: list[dict[str, Any]] = []
    feeders: list[dict[str, Any]] = []

    if result is not None:
        individual_results = _individual_load_results(project)
        contributions = {
            contribution.load_id: contribution
            for feeder_result in result.feeder_results
            for contribution in feeder_result.contributions
        }
        feeder_status = {
            feeder_result.feeder.feeder_id: (_enum_text(feeder_result.status) or "NON_CALCULABLE")
            for feeder_result in result.feeder_results
        }
        feeder_diagnostics = {
            feeder_result.feeder.feeder_id: _diagnostics(feeder_result.diagnostics)
            for feeder_result in result.feeder_results
        }
        boards = [_board_payload(item) for item in result.board_results]
        feeders = [_feeder_payload(item) for item in result.feeder_results]
    else:
        individual_results = {}
        contributions = {}
        feeder_status = {}
        feeder_diagnostics = {}

    for assignment in project.loads:
        feeder = feeder_map.get(assignment.feeder_id)
        if feeder is None:
            continue
        load_payloads.append(
            _load_payload(
                assignment,
                feeder,
                contributions.get(assignment.entry.load_id),
                feeder_status.get(assignment.feeder_id, "NON_CALCULABLE"),
                feeder_diagnostics.get(assignment.feeder_id, []),
                individual_results.get(assignment.entry.load_id),
            )
        )

    totals: dict[str, Any] = {
        "p_installed_w": None,
        "p_after_ku_w": None,
        "p_after_ks_w": None,
        "q_after_ku_var": None,
        "q_after_ks_var": None,
        "s_after_ku_va": None,
        "s_after_ks_va": None,
        "p_phases": {"l1": None, "l2": None, "l3": None},
        "q_phases": {"l1": None, "l2": None, "l3": None},
        "s_phases": {"l1": None, "l2": None, "l3": None},
        "current_phases": {"l1": None, "l2": None, "l3": None},
        "neutral_current_a": None,
        "unbalance_percent": None,
    }
    if result is not None:
        totals = {
            "p_installed_w": _text(result.p_installed_total_w),
            "p_after_ku_w": _text(result.p_after_ku_total_w),
            "p_after_ks_w": _text(result.p_after_ks_total_w),
            "q_after_ku_var": _text(result.q_after_ku_total_var),
            "q_after_ks_var": _text(result.q_after_ks_total_var),
            "s_after_ku_va": _text(result.s_after_ku_total_va),
            "s_after_ks_va": _text(result.s_after_ks_total_va),
            "p_phases": _phase_triplet(result.p_phases),
            "q_phases": _phase_triplet(result.q_phases),
            "s_phases": _phase_triplet(result.s_phases),
            "current_phases": _phase_triplet(result.current_phases),
            "neutral_current_a": _text(result.neutral_current_a),
            "unbalance_percent": _text(result.unbalance_percent),
        }

    diagnostics = (
        _diagnostics(result.diagnostics)
        if result is not None
        else [
            {
                "code": "CALCUL_INDISPONIBLE",
                "severity": "error",
                "message": "Le moteur n'a pas produit de résultat pour cette révision.",
                "field": None,
            }
        ]
    )

    assigned_ids = {
        assignment.entry.load_id for assignment in project.loads if assignment.feeder_id is not None
    }
    orphan_ids = sorted(
        assignment.entry.load_id
        for assignment in project.loads
        if assignment.feeder_id is not None and assignment.feeder_id not in feeder_map
    )
    missing_result_ids = sorted(load_id for load_id in assigned_ids if load_id not in contributions)
    unassigned_ids = sorted(
        assignment.entry.load_id for assignment in project.loads if assignment.feeder_id is None
    )
    calculation_current = state.get("calculation_revision") == state.get("revision")
    count_checks = [
        len(project.loads) == len(load_payloads),
        len(project.boards) == len(boards),
        len(project.feeders) == len(feeders),
    ]
    coherence_checks = [
        {
            "id": "engine_result",
            "label": "Résultat moteur disponible",
            "status": "PASS" if result is not None else "FAIL",
            "detail": "calculate_project_v13 a produit un résultat."
            if result is not None
            else "Aucun résultat moteur.",
        },
        {
            "id": "revision_current",
            "label": "Révision calculée à jour",
            "status": "PASS" if calculation_current else "WARN",
            "detail": (
                f"revision={state.get('revision')} · "
                f"calculation_revision={state.get('calculation_revision')}"
            ),
        },
        {
            "id": "row_counts",
            "label": "Cohérence des projections",
            "status": "PASS" if all(count_checks) else "FAIL",
            "detail": (
                f"récepteurs={len(load_payloads)}/{len(project.loads)} · "
                f"tableaux={len(boards)}/{len(project.boards)} · "
                f"départs={len(feeders)}/{len(project.feeders)}"
            ),
        },
        {
            "id": "orphan_loads",
            "label": "Récepteurs rattachés à un départ existant",
            "status": "PASS" if not orphan_ids else "FAIL",
            "detail": "Aucun récepteur orphelin."
            if not orphan_ids
            else f"{len(orphan_ids)} récepteur(s) orphelin(s).",
        },
        {
            "id": "receiver_results",
            "label": "Résultats individuels disponibles",
            "status": "PASS" if not missing_result_ids else "WARN",
            "detail": "Tous les récepteurs ont une contribution."
            if not missing_result_ids
            else f"{len(missing_result_ids)} récepteur(s) sans résultat individuel exposé.",
        },
        {
            "id": "unassigned_loads",
            "label": "Récepteurs non affectés",
            "status": "PASS" if not unassigned_ids else "WARN",
            "detail": "Aucun récepteur non affecté."
            if not unassigned_ids
            else f"{len(unassigned_ids)} récepteur(s) non affecté(s).",
        },
    ]
    if not all(count_checks) or result is None:
        coherence_status = "FAIL"
    elif any(item["status"] in {"WARN", "FAIL"} for item in coherence_checks):
        coherence_status = "WARN"
    else:
        coherence_status = "PASS"

    return {
        "project": {
            "id": project.project_id,
            "name": project.name,
            "reference": project.reference,
            "client": project.client or "",
            "client_id": client_id,
            "client_snapshot": client_snapshot,
            "description": project.description,
            "load_count": len(project.loads),
            "board_count": len(project.boards),
            "feeder_count": len(project.feeders),
            "unassigned_load_count": len(result.unassigned_load_ids) if result is not None else 0,
        },
        "engine": {
            "source": "SEGYRCALC V1.5 worktree · read-only",
            "facade": "calcelect.service_v13.calculate_project_v13",
            "version": result.engine_version if result is not None else "1.3.0",
            "mode": "project",
            "engine_source_sha256": PROJECT_SOURCE_SHA256,
            "fixture": state.get("file_path"),
            "data_class": data_class,
        },
        "status": _enum_text(result.status) if result is not None else "ERREUR",
        "is_calculable": bool(result.is_calculable) if result is not None else False,
        "calculated_at": result.calculated_at.isoformat() if result is not None else "",
        "totals": totals,
        "boards": boards,
        "feeders": feeders,
        "loads": load_payloads,
        "diagnostics": diagnostics,
        "assumptions": list(ASSUMPTIONS),
        "coherence": {
            "status": coherence_status,
            "checks": coherence_checks,
            "orphan_load_ids": orphan_ids,
            "missing_result_load_ids": missing_result_ids,
            "unassigned_load_ids": unassigned_ids,
        },
        "web": web,
        "state": state,
    }
