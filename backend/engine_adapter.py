"""Read-only adapter around the existing SEGYRCALC Python engine.

The adapter never copies, edits or re-implements calculation rules. It imports
the already-qualified V1.5 worktree source and converts dataclasses/Decimals to
JSON-safe values for the local web interface.
"""

from __future__ import annotations

import hashlib
import os
import sys
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from .distribution import distribution_type_for

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENGINE_SRC = (
    PROJECT_ROOT.parent.parent / "SEGYRCALC-V1.5-UI-ERGONOMIE-01" / "worktree" / "src"
)
DEFAULT_FIXTURE = (
    PROJECT_ROOT.parent.parent
    / "SEGYRCALC-V1.5-UI-ERGONOMIE-01"
    / "worktree"
    / "examples"
    / "recette-business-acceptance-v1.3.json"
)

ASSUMPTIONS = (
    "Régime sinusoïdal établi, valeurs RMS.",
    "Triphasé équilibré pour le calcul B3-01 ; phases L1=0°, L2=-120°, L3=+120°.",
    "Le facteur de puissance est assimilé à cos φ.",
    "Q positif par convention inductive ; aucun harmonique, défaut ou sélectivité.",
    "Arithmétique Decimal à 50 chiffres, arrondi ROUND_HALF_EVEN.",
)


class EngineUnavailable(RuntimeError):
    """Raised when the read-only engine source cannot be imported."""


def _resolve_engine_src() -> Path:
    configured = os.environ.get("SEGYR_ENGINE_SRC")
    candidate = Path(configured).expanduser().resolve() if configured else DEFAULT_ENGINE_SRC
    if not (candidate / "segyr_calc" / "core" / "power.py").is_file():
        raise EngineUnavailable(
            "Source moteur introuvable. Définir SEGYR_ENGINE_SRC vers "
            "SEGYRCALC-V1.5-UI-ERGONOMIE-01/worktree/src."
        )
    if not (candidate / "calcelect" / "service_v13.py").is_file():
        raise EngineUnavailable(
            "La façade calcelect.service_v13 est absente de la source configurée."
        )
    return candidate


def _resolve_fixture() -> Path:
    configured = os.environ.get("SEGYR_PROJECT_FIXTURE")
    candidate = Path(configured).expanduser().resolve() if configured else DEFAULT_FIXTURE
    if not candidate.is_file():
        raise EngineUnavailable(f"Jeu de données réel introuvable : {candidate}")
    return candidate


ENGINE_SRC = _resolve_engine_src()
FIXTURE = _resolve_fixture()
if str(ENGINE_SRC) not in sys.path:
    sys.path.insert(0, str(ENGINE_SRC))

# Imports deliberately happen after the read-only source path is installed.
from calcelect.persistence_v13 import load_project_v13  # noqa: E402
from calcelect.service_v11 import calculate_project_v11  # noqa: E402
from calcelect.service_v13 import calculate_project_v13  # noqa: E402
from segyr_calc.core.numbers import canonical_string  # noqa: E402
from segyr_calc.core.power import calculate_power  # noqa: E402

POWER_SOURCE = ENGINE_SRC / "segyr_calc" / "core" / "power.py"
PROJECT_SOURCE = ENGINE_SRC / "calcelect" / "service_v13.py"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


POWER_SOURCE_SHA256 = _sha256(POWER_SOURCE)
PROJECT_SOURCE_SHA256 = _sha256(PROJECT_SOURCE)


def _text(value: Decimal | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return canonical_string(value)
    return str(value)


def _enum_text(value: Enum | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _phase_triplet(value: Any) -> dict[str, str | None]:
    return {"l1": _text(value.l1), "l2": _text(value.l2), "l3": _text(value.l3)}


def _diagnostics(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [
        {
            "code": str(item.code),
            "severity": str(item.severity),
            "message": str(item.message),
            "field": getattr(item, "field", None),
        }
        for item in items
    ]


def normalize_decimal_text(value: str) -> str:
    """Accept the French comma used by the UI while keeping engine parsing strict."""
    stripped = value.strip().replace(" ", "").replace("\u202f", "")
    if "," in stripped and "." not in stripped:
        return stripped.replace(",", ".")
    return stripped


def calculate_power_payload(request: dict[str, Any]) -> dict[str, Any]:
    """Call the real B3-01 function and return a JSON-safe result."""
    efficiency = request.get("efficiency")
    efficiency_unit = "fraction"
    if efficiency:
        cleaned = normalize_decimal_text(str(efficiency)).rstrip("%").strip()
        numeric = Decimal(cleaned)
        if "%" in str(efficiency) or numeric > 1:
            efficiency_unit = "percent"
        efficiency = cleaned

    result = calculate_power(
        mode=str(request["mode"]),
        network=str(request["network"]),
        voltage_v=normalize_decimal_text(str(request["voltage_v"])),
        power_value=normalize_decimal_text(str(request["power_value"])),
        power_unit=str(request["power_unit"]),
        power_factor=normalize_decimal_text(str(request["power_factor"])),
        power_nature=str(request.get("power_nature", "ABSORBED")),
        efficiency=efficiency,
        efficiency_unit=efficiency_unit,
    )

    return {
        "status": _enum_text(result.status),
        "mode": _enum_text(result.mode),
        "network": _enum_text(result.network),
        "power_nature": _enum_text(result.power_nature),
        "p_abs_w": _text(result.p_abs_w),
        "p_useful_w": _text(result.p_useful_w),
        "s_va": _text(result.s_va),
        "q_var": _text(result.q_var),
        "current_a": _text(result.current_a),
        "voltage_v": _text(result.voltage_v),
        "power_factor": _text(result.power_factor),
        "efficiency": _text(result.efficiency),
        "diagnostics": _diagnostics(result.diagnostics),
        "engine": {
            "source": "SEGYRCALC V1.5 worktree · read-only",
            "function": "segyr_calc.core.power.calculate_power",
            "source_sha256": POWER_SOURCE_SHA256,
        },
    }


def _physical_load_ids(
    board: Any,
    ancestors: frozenset[str] = frozenset(),
) -> frozenset[str]:
    """Return the unique receiver ids fed by a board and its downstream boards.

    This projection belongs to the web adapter so the external engine source
    stays read-only. Phase contributions identify the physical receivers; the
    legacy engine ``load_count`` is intentionally not used because it sums
    per-phase contributions and therefore counts a three-phase receiver three
    times.
    """
    board_id = str(board.board.board_id)
    if board_id in ancestors:
        # The engine rejects cyclic topologies before calculation. Keep this
        # guard so a corrupt intermediate result can never recurse forever.
        return frozenset()

    ancestors = ancestors | {board_id}
    load_ids: set[str] = set()
    for feeder in board.feeder_results:
        load_ids.update(str(item.load_id) for item in feeder.contributions)
        if feeder.downstream_board is not None:
            load_ids.update(_physical_load_ids(feeder.downstream_board, ancestors))
    return frozenset(load_ids)


def _board_payload(board: Any) -> dict[str, Any]:
    return {
        "id": str(board.board.board_id),
        "designation": str(board.board.designation),
        "type": _enum_text(board.board.board_type),
        "network": _enum_text(board.board.network),
        "voltage_v": _text(board.board.voltage_v),
        "parent_feeder_id": board.board.parent_feeder_id,
        "phase_voltage_v": _text(board.phase_voltage_v),
        "has_neutral": bool(board.board.has_neutral),
        "p_installed_w": _text(board.p_installed_w),
        "p_after_ku_w": _text(board.p_after_ku_w),
        "p_after_ks_w": _text(board.p_after_ks_w),
        "q_after_ku_var": _text(board.q_after_ku_var),
        "q_after_ks_var": _text(board.q_after_ks_var),
        "s_after_ku_va": _text(board.s_after_ku_va),
        "s_after_ks_va": _text(board.s_after_ks_va),
        "p_phases": _phase_triplet(board.p_phases),
        "q_phases": _phase_triplet(board.q_phases),
        "s_phases": _phase_triplet(board.s_phases),
        "current_phases": _phase_triplet(board.current_phases),
        "neutral_current_a": _text(board.neutral_current_a),
        "unbalance_percent": _text(board.unbalance_percent),
        "status": _enum_text(board.status),
        "feeder_count": int(board.feeder_count),
        "load_count": len(_physical_load_ids(board)),
        "diagnostics": _diagnostics(board.diagnostics),
    }


def _individual_load_results(project: Any) -> dict[str, dict[str, Any]]:
    """Return the engine's complete per-load contribution after Ku and Ks.

    The V1.3 phase result stores per-phase P/Q contributions for triphasé
    receivers. Those values must not be presented as receiver totals. The
    existing V1.1 service retains the complete ``GroupContribution`` and
    ``KsContribution`` objects, which carry total receiver P/Q/S/I values.
    This adapter only reads those existing results; it does not evaluate a
    formula or modify the project.
    """
    try:
        result = calculate_project_v11(project)
    except Exception:
        return {}

    def from_group(contribution: Any) -> dict[str, Any]:
        return {
            "p_after_ku_w": contribution.p_used_after_w,
            "q_after_ku_var": contribution.q_used_after_var,
            "p_after_ks_w": contribution.p_used_after_w,
            "q_after_ks_var": contribution.q_used_after_var,
            "s_after_ks_va": contribution.s_used_after_va,
            "current_a": contribution.current_after_a,
        }

    values: dict[str, dict[str, Any]] = {}
    for feeder_result in result.feeder_results:
        if feeder_result.ks_result is not None:
            for contribution in feeder_result.ks_result.contributions:
                source = contribution.source
                values[contribution.load_id] = {
                    "p_after_ku_w": source.p_used_after_w,
                    "q_after_ku_var": source.q_used_after_var,
                    "p_after_ks_w": contribution.p_after_w,
                    "q_after_ks_var": contribution.q_after_var,
                    "s_after_ks_va": contribution.s_after_va,
                    "current_a": contribution.current_after_a,
                }
        elif feeder_result.group_result is not None:
            for contribution in feeder_result.group_result.contributions:
                values[contribution.load_id] = from_group(contribution)
    return values


def _load_payload(
    assignment: Any,
    feeder: Any,
    contribution: Any | None,
    feeder_status: str,
    diagnostics: list[dict[str, Any]],
    individual_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = assignment.entry
    individual = individual_result or {}
    load = entry.load

    def value(name: str, fallback: Any = None) -> str | None:
        selected = individual.get(name)
        if selected is None:
            selected = fallback
        return _text(selected)

    individual_s = individual.get("s_after_ks_va")
    individual_i = individual.get("current_a")
    return {
        "id": str(load.load_id),
        "designation": str(load.designation),
        "network": _enum_text(load.network),
        "voltage_v": _text(load.voltage_v),
        "nominal_power": _text(load.nominal_power),
        "power_unit": _enum_text(load.power_unit),
        "quantity": int(load.quantity),
        "installed_power_w": _text(load.installed_power_w),
        "power_factor": _text(load.power_factor),
        "ku": _text(entry.ku_value),
        "ks": _text(feeder.ks),
        "feeder_id": str(assignment.feeder_id),
        "parent_board_id": str(feeder.parent_board_id),
        "phase": _enum_text(assignment.phase),
        "p_after_ku_w": value(
            "p_after_ku_w", contribution.p_after_ku_w if contribution else None
        ),
        "q_after_ku_var": value(
            "q_after_ku_var", contribution.q_after_ku_var if contribution else None
        ),
        "p_after_ks_w": value(
            "p_after_ks_w", contribution.p_after_ks_w if contribution else None
        ),
        "q_after_ks_var": value(
            "q_after_ks_var", contribution.q_after_ks_var if contribution else None
        ),
        "s_after_ks_va": _text(individual_s),
        "current_a": _text(individual_i),
        "current_real_a": _text(contribution.current_real_a) if contribution else None,
        "current_imag_a": _text(contribution.current_imag_a) if contribution else None,
        "current_available": individual_i is not None,
        "apparent_power_available": individual_s is not None,
        "status": feeder_status if contribution else "NON_CALCULABLE",
        "diagnostics": diagnostics
        if contribution
        else [
            {
                "code": "RESULTAT_RECEPTEUR_NON_EXPOSE",
                "severity": "warning",
                "message": "Le moteur n'expose pas de résultat individuel pour ce récepteur.",
                "field": "load",
            }
        ],
    }


def _feeder_payload(feeder: Any) -> dict[str, Any]:
    return {
        "id": str(feeder.feeder.feeder_id),
        "designation": str(feeder.feeder.designation),
        "parent_board_id": str(feeder.feeder.parent_board_id),
        "network": _enum_text(feeder.feeder.network),
        "voltage_v": _text(feeder.feeder.voltage_v),
        "phase_voltage_v": _text(feeder.phase_voltage_v),
        "voltage_ln_v": _text(feeder.feeder.voltage_ln_v),
        "description": str(feeder.feeder.description),
        "has_neutral": feeder.feeder.has_neutral,
        "distribution_type": distribution_type_for(feeder.feeder),
        "phase": _enum_text(feeder.feeder.phase),
        "ks": _text(feeder.ks),
        "member_count": len(feeder.feeder.member_load_ids),
        "downstream_board_id": feeder.feeder.downstream_board_id,
        "p_installed_w": _text(feeder.p_installed_w),
        "p_after_ku_w": _text(feeder.p_after_ku_w),
        "p_after_ks_w": _text(feeder.p_after_ks_w),
        "q_after_ku_var": _text(feeder.q_after_ku_var),
        "q_after_ks_var": _text(feeder.q_after_ks_var),
        "s_after_ku_va": _text(feeder.s_after_ku_va),
        "s_after_ks_va": _text(feeder.s_after_ks_va),
        "p_phases": _phase_triplet(feeder.p_phases),
        "q_phases": _phase_triplet(feeder.q_phases),
        "s_phases": _phase_triplet(feeder.s_phases),
        "current_phases": _phase_triplet(feeder.current_phases),
        "neutral_current_a": _text(feeder.neutral_current_a),
        "unbalance_percent": _text(feeder.unbalance_percent),
        "status": _enum_text(feeder.status),
        "diagnostics": _diagnostics(feeder.diagnostics),
    }


def load_project_payload() -> dict[str, Any]:
    """Load the real V1.3 fixture and calculate it with the qualified facade."""
    project = load_project_v13(FIXTURE)
    result = calculate_project_v13(project)
    individual_results = _individual_load_results(project)
    feeder_map = {feeder.feeder_id: feeder for feeder in project.feeders}
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
    load_payloads = []
    for assignment in project.loads:
        feeder = feeder_map[assignment.feeder_id]
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
    return {
        "project": {
            "name": project.name,
            "reference": project.reference,
            "client": project.client or "",
            "load_count": len(project.loads),
            "board_count": len(project.boards),
            "feeder_count": len(project.feeders),
            "unassigned_load_count": len(result.unassigned_load_ids),
        },
        "engine": {
            "source": "SEGYRCALC V1.5 worktree · read-only",
            "facade": "calcelect.service_v13.calculate_project_v13",
            "version": result.engine_version,
            "mode": "project",
            "engine_source_sha256": PROJECT_SOURCE_SHA256,
            "fixture": str(FIXTURE),
            "data_class": "REAL_ENGINE_FIXTURE",
        },
        "status": _enum_text(result.status),
        "is_calculable": bool(result.is_calculable),
        "calculated_at": result.calculated_at.isoformat(),
        "totals": {
            "p_installed_w": _text(result.p_installed_total_w),
            "p_after_ku_w": _text(result.p_after_ku_total_w),
            "p_after_ks_w": _text(result.p_after_ks_total_w),
            "q_after_ku_var": _text(result.q_after_ku_total_var),
            "q_after_ks_var": _text(result.q_after_ks_total_var),
            "s_after_ku_va": _text(result.s_after_ku_total_va),
            "s_after_ks_va": _text(result.s_after_ks_total_va),
            "p_phases": _phase_triplet(result.p_phases),
            "current_phases": _phase_triplet(result.current_phases),
            "neutral_current_a": _text(result.neutral_current_a),
            "unbalance_percent": _text(result.unbalance_percent),
        },
        "boards": [_board_payload(item) for item in result.board_results],
        "feeders": [_feeder_payload(item) for item in result.feeder_results],
        "loads": load_payloads,
        # The reference fixture has no unassigned receiver. Keep the additive
        # field present for consumers of this secondary fixture endpoint.
        "unassigned_loads": [],
        "diagnostics": _diagnostics(result.diagnostics),
        "assumptions": list(ASSUMPTIONS),
    }
