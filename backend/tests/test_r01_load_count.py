from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.engine_adapter import (  # noqa: F401  (installs the read-only engine path)
    ENGINE_SRC,
    _board_payload,
    _physical_load_ids,
)
from calcelect.hierarchy import Board, BoardType, Feeder, LoadAssignment, Phase, ProjectV11
from calcelect.models import LoadEntry
from calcelect.phase_service import calculate_project_v12
from segyr_calc.a2 import Load
from segyr_calc.core.power import Network
from segyr_calc.core.units import Unit


def _load(
    load_id: str,
    *,
    designation: str | None = None,
    network: Network,
    phase: Phase | None,
) -> LoadAssignment:
    voltage = Decimal("400") if network is Network.TRI else Decimal("230")
    load = Load(
        load_id,
        designation or load_id,
        network,
        voltage,
        Decimal("1000"),
        Unit.W,
        1,
        Decimal("0.9"),
    )
    return LoadAssignment(LoadEntry(load, Decimal("1")), phase=phase)


def _root() -> Board:
    return Board(
        "TGBT",
        "TGBT",
        BoardType.TGBT,
        Network.TRI,
        Decimal("400"),
        has_neutral=True,
        voltage_ln_v=Decimal("230"),
    )


def _single_board(loads: list[LoadAssignment]) -> ProjectV11:
    project = ProjectV11.new(name="R01", reference="R01")
    for load in loads:
        project = project.add_load(load)
    project = project.add_board(_root())
    return project.add_feeder_with_loads(
        Feeder(
            "D1",
            "D1",
            "TGBT",
            Network.TRI,
            Decimal("400"),
            voltage_ln_v=Decimal("230"),
            member_load_ids=tuple(item.entry.load.load_id for item in loads),
        ),
        tuple(item.entry.load.load_id for item in loads),
    )


def _child(project: ProjectV11, board_id: str, feeder_id: str, parent_board_id: str = "TGBT") -> ProjectV11:
    return project.add_board_with_feeder(
        Board(
            board_id,
            board_id,
            BoardType.DIVISIONNAIRE,
            Network.TRI,
            Decimal("400"),
            parent_feeder_id=feeder_id,
            has_neutral=True,
            voltage_ln_v=Decimal("230"),
        ),
        Feeder(
            feeder_id,
            feeder_id,
            parent_board_id,
            Network.TRI,
            Decimal("400"),
            downstream_board_id=board_id,
        ),
    )


def _add_feeder_load(project: ProjectV11, feeder_id: str, board_id: str, load_id: str) -> ProjectV11:
    return project.add_feeder_with_loads(
        Feeder(
            feeder_id,
            feeder_id,
            board_id,
            Network.TRI,
            Decimal("400"),
            voltage_ln_v=Decimal("230"),
            member_load_ids=(load_id,),
        ),
        (load_id,),
    )


def _board_payloads(result: Any) -> dict[str, dict[str, Any]]:
    return {
        str(item.board.board_id): _board_payload(item)
        for item in result.board_results
    }


def test_r01_tri_counts_as_one_physical_receiver() -> None:
    project = _single_board([
        _load("T1", network=Network.TRI, phase=None),
    ])
    result = calculate_project_v12(project)
    assert result.load_count == 1
    assert result.root_board is not None
    payload = _board_payload(result.root_board)
    assert payload["load_count"] == 1
    assert _physical_load_ids(result.root_board) == frozenset({"T1"})
    assert len(result.root_board.feeder_results[0].contributions) == 3
    assert result.p_after_ku_total_w == Decimal("1000")


def test_r01_multiple_and_mixed_receivers_are_unique() -> None:
    result = calculate_project_v12(_single_board([
        _load("L1", network=Network.MONO, phase=Phase.L1),
        _load("T1", network=Network.TRI, phase=None),
        _load("T2", network=Network.TRI, phase=None),
    ]))
    assert result.load_count == 3
    assert result.root_board is not None
    boards = _board_payloads(result)
    assert boards["TGBT"]["load_count"] == 3
    assert _physical_load_ids(result.root_board) == frozenset({"L1", "T1", "T2"})


def test_r01_same_designation_does_not_merge_ids() -> None:
    result = calculate_project_v12(_single_board([
        _load("A", designation="Même libellé", network=Network.MONO, phase=Phase.L1),
        _load("B", designation="Même libellé", network=Network.MONO, phase=Phase.L2),
    ]))
    assert result.root_board is not None
    boards = _board_payloads(result)
    assert boards["TGBT"]["load_count"] == 2
    assert _physical_load_ids(result.root_board) == frozenset({"A", "B"})


def test_r01_downstream_and_cascade_are_recursive_on_each_ancestor() -> None:
    project = ProjectV11.new(name="R01 cascade", reference="R01-C")
    project = project.add_load(_load("T1", network=Network.TRI, phase=None))
    project = project.add_board(_root())
    project = _child(project, "TD1", "D-TD1")
    project = _child(project, "TD2", "D-TD2", parent_board_id="TD1")
    project = project.add_feeder_with_loads(
        Feeder(
            "D-LOAD",
            "D-LOAD",
            "TD2",
            Network.TRI,
            Decimal("400"),
            voltage_ln_v=Decimal("230"),
            member_load_ids=("T1",),
        ),
        ("T1",),
    )
    result = calculate_project_v12(project)
    by_id = {item.board.board_id: item for item in result.board_results}
    boards = _board_payloads(result)
    assert result.load_count == 1
    assert boards["TGBT"]["load_count"] == 1
    assert boards["TD1"]["load_count"] == 1
    assert boards["TD2"]["load_count"] == 1
    assert _physical_load_ids(by_id["TGBT"]) == frozenset({"T1"})
    assert _physical_load_ids(by_id["TD1"]) == frozenset({"T1"})
    assert _physical_load_ids(by_id["TD2"]) == frozenset({"T1"})


def test_r01_multiple_downstream_union() -> None:
    project = ProjectV11.new(name="R01 union", reference="R01-U")
    project = project.add_load(_load("T1", network=Network.TRI, phase=None))
    project = project.add_load(_load("T2", network=Network.TRI, phase=None))
    project = project.add_board(_root())
    project = _child(project, "TD1", "D-TD1")
    project = _child(project, "TD2", "D-TD2")
    project = _add_feeder_load(project, "D1", "TD1", "T1")
    project = _add_feeder_load(project, "D2", "TD2", "T2")
    result = calculate_project_v12(project)
    by_id = {item.board.board_id: item for item in result.board_results}
    boards = _board_payloads(result)
    assert result.load_count == 2
    assert boards["TGBT"]["load_count"] == 2
    assert boards["TD1"]["load_count"] == 1
    assert boards["TD2"]["load_count"] == 1
    assert _physical_load_ids(by_id["TGBT"]) == frozenset({"T1", "T2"})


def test_r01_direct_and_downstream_mixed_perimeter() -> None:
    project = ProjectV11.new(name="R01 mixed", reference="R01-M")
    project = project.add_load(_load("D", network=Network.TRI, phase=None))
    project = project.add_load(_load("C", network=Network.TRI, phase=None))
    project = project.add_board(_root())
    project = _child(project, "TD1", "D-TD1")
    project = _add_feeder_load(project, "D-DIRECT", "TGBT", "D")
    project = _add_feeder_load(project, "D-CHILD", "TD1", "C")
    result = calculate_project_v12(project)
    by_id = {item.board.board_id: item for item in result.board_results}
    boards = _board_payloads(result)
    assert result.load_count == 2
    assert boards["TGBT"]["load_count"] == 2
    assert boards["TD1"]["load_count"] == 1
    assert _physical_load_ids(by_id["TGBT"]) == frozenset({"D", "C"})
