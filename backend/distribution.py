"""Distribution semantics for outgoing feeders (WEB-08 Lot 3).

``distribution_type`` is a request/presentation value. The persisted model
remains the existing ``Feeder`` fields: network, voltage_v, has_neutral,
voltage_ln_v and phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

DISTRIBUTION_TYPES = ("MONO_N", "TRI_NO_N", "TRI_N")
PHASES = ("L1", "L2", "L3")


@dataclass(frozen=True, slots=True)
class DistributionError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def _network(value: Any) -> str:
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw).strip().upper()


def _voltage(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def distribution_type_for(feeder: Any) -> str:
    if _network(feeder.network) == "MONO":
        return "MONO_N"
    return "TRI_N" if feeder.has_neutral else "TRI_NO_N"


def allowed_distribution_types(parent: Any) -> tuple[str, ...]:
    network = _network(parent.network)
    neutral = bool(parent.has_neutral)
    line_voltage = _voltage(parent.voltage_ln_v)
    if network == "MONO":
        return ("MONO_N",) if neutral else ()
    if network == "TRI":
        result: list[str] = ["TRI_NO_N"]
        if neutral and line_voltage is not None:
            result.append("MONO_N")
            result.append("TRI_N")
        return tuple(result)
    return ()


def default_distribution_type(parent: Any) -> str | None:
    allowed = allowed_distribution_types(parent)
    if not allowed:
        return None
    if "TRI_N" in allowed:
        return "TRI_N"
    if "TRI_NO_N" in allowed:
        return "TRI_NO_N"
    return "MONO_N"


def _canonical_phase(value: Any, *, required: bool) -> str | None:
    if value is None or str(value).strip() == "":
        if required:
            raise DistributionError(
                "PHASE_REQUISE",
                "Une phase L1, L2 ou L3 est requise pour un départ monophasé.",
            )
        return None
    phase = str(value).strip().upper()
    if phase not in PHASES:
        raise DistributionError("PHASE_INVALIDE", "La phase doit être L1, L2 ou L3.")
    return phase


def _fields_for_type(parent: Any, distribution_type: str, phase: Any) -> dict[str, Any]:
    network = _network(parent.network)
    parent_voltage = _voltage(parent.voltage_v)
    parent_ln = _voltage(parent.voltage_ln_v)
    neutral = bool(parent.has_neutral)

    if distribution_type == "MONO_N":
        if not neutral:
            raise DistributionError(
                "NEUTRE_ABSENT",
                "Un départ monophasé exige un neutre disponible sur le tableau amont.",
            )
        if network == "MONO":
            voltage = parent_voltage or parent_ln
            voltage_ln = parent_ln or parent_voltage
        else:
            voltage = parent_ln
            voltage_ln = parent_ln
        if voltage is None:
            raise DistributionError(
                "TENSION_SIMPLE_ABSENT",
                "La tension phase-neutre du tableau amont est absente.",
            )
        return {
            "network": "MONO",
            "voltage_v": voltage,
            "voltage_ln_v": voltage_ln or voltage,
            "has_neutral": True,
            "phase": _canonical_phase(phase, required=True),
        }

    if network != "TRI":
        raise DistributionError(
            "RESEAU_INCOMPATIBLE",
            "Un départ triphasé ne peut pas être créé sur un tableau monophasé.",
        )

    if parent_voltage is None:
        raise DistributionError(
            "TENSION_INVALIDE",
            "La tension composée du tableau amont est absente.",
        )
    if phase is not None and str(phase).strip() != "":
        raise DistributionError(
            "PHASE_INVALIDE",
            "Un départ triphasé ne porte pas de phase unique.",
        )

    if distribution_type == "TRI_NO_N":
        return {
            "network": "TRI",
            "voltage_v": parent_voltage,
            "voltage_ln_v": None,
            "has_neutral": False,
            "phase": None,
        }

    if distribution_type == "TRI_N":
        if not neutral:
            raise DistributionError(
                "NEUTRE_ABSENT",
                "Un départ triphasé + N exige un neutre disponible sur le tableau amont.",
            )
        if parent_ln is None:
            raise DistributionError(
                "TENSION_SIMPLE_ABSENT",
                "La tension phase-neutre est absente pour ce départ triphasé + N.",
            )
        return {
            "network": "TRI",
            "voltage_v": parent_voltage,
            "voltage_ln_v": parent_ln,
            "has_neutral": True,
            "phase": None,
        }

    raise DistributionError("DISTRIBUTION_INVALIDE", "Type de distribution inconnu.")


def _legacy_fields(parent: Any, payload: dict[str, Any], existing: Any | None) -> dict[str, Any]:
    """Compatibility path for 0.7.1 callers that do not send a type."""

    network = _network(
        payload.get("network")
        or (getattr(existing, "network", None) if existing is not None else parent.network)
    )
    if network not in {"MONO", "TRI"}:
        raise DistributionError("RESEAU_INVALIDE", "Le réseau doit être MONO ou TRI.")

    phase = payload.get("phase", getattr(existing, "phase", None) if existing else None)
    phase = _canonical_phase(phase, required=False)
    if network == "TRI" and phase is not None:
        # This is the invariant that produced the original UI error.
        raise DistributionError(
            "PHASE_INVALIDE",
            "Un départ triphasé ne porte pas de phase unique.",
        )

    if network == "MONO":
        if not bool(parent.has_neutral):
            raise DistributionError(
                "NEUTRE_ABSENT",
                "Un départ monophasé exige un neutre disponible sur le tableau amont.",
            )
        voltage = _voltage(payload.get("voltage_v"))
        if voltage is None and existing is not None:
            voltage = _voltage(existing.voltage_v)
        voltage = voltage or _voltage(parent.voltage_ln_v) or _voltage(parent.voltage_v)
        voltage_ln = _voltage(payload.get("voltage_ln_v"))
        if voltage_ln is None and existing is not None:
            voltage_ln = _voltage(existing.voltage_ln_v)
        voltage_ln = voltage_ln or _voltage(parent.voltage_ln_v) or voltage
        has_neutral = True
    else:
        voltage = _voltage(payload.get("voltage_v"))
        if voltage is None and existing is not None:
            voltage = _voltage(existing.voltage_v)
        voltage = voltage or _voltage(parent.voltage_v)
        raw_neutral = payload.get("has_neutral")
        if raw_neutral is None and existing is not None:
            raw_neutral = existing.has_neutral
        if raw_neutral is None:
            raw_neutral = bool(parent.has_neutral)
        has_neutral = bool(raw_neutral)
        voltage_ln = _voltage(payload.get("voltage_ln_v"))
        if voltage_ln is None and existing is not None:
            voltage_ln = _voltage(existing.voltage_ln_v)
        if not has_neutral:
            voltage_ln = None
        elif voltage_ln is None:
            voltage_ln = _voltage(parent.voltage_ln_v)

    if network == "MONO" and voltage is None:
        raise DistributionError("TENSION_INVALIDE", "La tension du départ est absente.")
    if network == "TRI" and voltage is None:
        raise DistributionError("TENSION_INVALIDE", "La tension du départ est absente.")
    if phase is not None and network != "MONO":
        raise DistributionError(
            "PHASE_INVALIDE",
            "Un départ triphasé ne porte pas de phase unique.",
        )
    return {
        "network": network,
        "voltage_v": voltage,
        "voltage_ln_v": voltage_ln,
        "has_neutral": has_neutral,
        "phase": phase,
    }


def resolve_distribution(
    parent: Any,
    payload: dict[str, Any],
    *,
    existing: Any | None = None,
) -> dict[str, Any]:
    """Resolve a request to persisted Feeder fields.

    An explicit ``distribution_type`` always wins. Without it, the legacy
    fields are preserved for 0.7.1 callers, but a phase on a triphasé feeder is
    rejected instead of being silently accepted.
    """

    explicit = payload.get("distribution_type")
    if explicit:
        value = str(explicit).strip().upper()
        if value not in DISTRIBUTION_TYPES:
            raise DistributionError("DISTRIBUTION_INVALIDE", "Type de distribution inconnu.")
        if value not in allowed_distribution_types(parent):
            raise DistributionError(
                "DISTRIBUTION_INCOMPATIBLE",
                "Ce type de distribution est incompatible avec le tableau amont.",
            )
        return _fields_for_type(parent, value, payload.get("phase"))

    return _legacy_fields(parent, payload, existing)
