from __future__ import annotations

import json
from decimal import Decimal

import pytest

from backend.project_payload import build_project_payload
from calcelect.hierarchy import Board, BoardType, Feeder, LoadAssignment, ProjectV11
from calcelect.models import LoadEntry
from calcelect.service_v13 import calculate_project_v13
from segyr_calc.a2.models import Load


def make_project(*, assigned: bool = False, unassigned: int = 0) -> ProjectV11:
    project = ProjectV11.new(name="UAT", reference="UAT").add_board(Board(
        board_id="TGBT-01",
        designation="TGBT UAT",
        board_type=BoardType.TGBT,
        network="TRI",
        voltage_v="400",
        has_neutral=True,
        voltage_ln_v="230",
    ))
    if assigned:
        project = project.add_feeder(Feeder(
            feeder_id="DEP-01",
            designation="Départ UAT",
            parent_board_id="TGBT-01",
            network="TRI",
            voltage_v="400",
            has_neutral=True,
            draft=True,
        ))
        project = project.add_load(LoadAssignment(
            entry=LoadEntry(load=Load(
                load_id="REC-A",
                designation="Récepteur affecté",
                network="TRI",
                voltage_v="400",
                nominal_power="1000",
                power_unit="W",
                quantity=1,
                power_factor=Decimal("0.9"),
            ), ku="0.8"),
            feeder_id="DEP-01",
        ))
    for index in range(unassigned):
        project = project.add_load(LoadAssignment(
            entry=LoadEntry(load=Load(
                load_id=f"REC-U{index + 1}",
                designation=f"Récepteur non affecté {index + 1}",
                network="TRI",
                voltage_v="400",
                nominal_power="1200",
                power_unit="W",
                quantity=1,
                power_factor=Decimal("0.9"),
            ), ku="0.7"),
            feeder_id=None,
        ))
    return project


def payload_for(project: ProjectV11) -> dict:
    result = calculate_project_v13(project)
    return build_project_payload(
        project,
        result,
        web={},
        state={"revision": 1, "calculation_revision": 1},
    )


def test_no_unassigned_receiver_returns_empty_list() -> None:
    payload = payload_for(make_project())
    assert payload["loads"] == []
    assert payload["unassigned_loads"] == []
    assert payload["project"]["load_count"] == 0
    assert payload["project"]["unassigned_load_count"] == 0


def test_one_unassigned_receiver_preserves_identity_and_input_fields() -> None:
    payload = payload_for(make_project(unassigned=1))
    assert payload["loads"] == []
    row = payload["unassigned_loads"][0]
    assert row["id"] == "REC-U1"
    assert row["designation"] == "Récepteur non affecté 1"
    assert row["feeder_id"] == ""
    assert row["parent_board_id"] == ""
    assert row["ks"] is None
    assert row["p_after_ku_w"] is None
    assert row["p_after_ks_w"] is None
    assert row["installed_power_w"] == "1200"
    assert row["ku"] == "0.7"
    assert row["status"] == "NON_AFFECTE"
    assert row["diagnostics"][0]["code"] == "RECEPTEUR_NON_AFFECTE"


def test_multiple_unassigned_receivers_are_deterministic() -> None:
    payload = payload_for(make_project(unassigned=3))
    assert [row["id"] for row in payload["unassigned_loads"]] == [
        "REC-U1", "REC-U2", "REC-U3",
    ]
    assert payload["project"]["unassigned_load_count"] == 3
    assert payload["project"]["load_count"] == 3


def test_mixed_receivers_are_exclusive_and_counters_coherent() -> None:
    payload = payload_for(make_project(assigned=True, unassigned=2))
    assert [row["id"] for row in payload["loads"]] == ["REC-A"]
    assert [row["id"] for row in payload["unassigned_loads"]] == ["REC-U1", "REC-U2"]
    assert payload["project"]["load_count"] == 3
    assert payload["project"]["unassigned_load_count"] == 2
    assert len(payload["loads"]) + len(payload["unassigned_loads"]) == payload["project"]["load_count"]
    assert not ({row["id"] for row in payload["loads"]} & {
        row["id"] for row in payload["unassigned_loads"]
    })


def test_json_serialization_and_old_consumer_tolerance() -> None:
    payload = payload_for(make_project(unassigned=2))
    serialized = json.dumps(payload, ensure_ascii=False)
    restored = json.loads(serialized)
    assert restored["unassigned_loads"][0]["id"] == "REC-U1"
    assert restored["project"]["unassigned_load_count"] == 2
    # An old consumer can ignore the additive field entirely.
    assert set(restored) >= {"project", "loads", "unassigned_loads", "coherence"}


def test_assigned_result_is_not_changed_by_adding_unassigned_receiver() -> None:
    assigned_only = payload_for(make_project(assigned=True))
    mixed = payload_for(make_project(assigned=True, unassigned=1))
    assert assigned_only["loads"][0]["id"] == mixed["loads"][0]["id"]
    for field in (
        "installed_power_w", "p_after_ku_w", "q_after_ku_var",
        "p_after_ks_w", "q_after_ks_var", "s_after_ks_va", "current_a",
    ):
        assert assigned_only["loads"][0][field] == mixed["loads"][0][field]


def test_missing_feeder_id_is_rejected_by_the_model_not_reclassified() -> None:
    project = make_project()
    with pytest.raises(Exception) as captured:
        project.add_load(LoadAssignment(
            entry=LoadEntry(load=Load(
                load_id="REC-BAD",
                designation="Récepteur invalide",
                network="TRI",
                voltage_v="400",
                nominal_power="1000",
                power_unit="W",
                quantity=1,
                power_factor=Decimal("0.9"),
            ), ku="1"),
            feeder_id="MISSING",
        ))
    assert getattr(captured.value, "code", "DEPART_INTROUVABLE") == "DEPART_INTROUVABLE"
