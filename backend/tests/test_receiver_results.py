from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.engine_adapter import _load_payload, _text
from backend.main import create_app
from backend.project_commands import CommandProjectStore
from backend.project_payload import build_project_payload

TOKEN = "web08-r6-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def _client(tmp_path: Path) -> tuple[CommandProjectStore, TestClient]:
    store = CommandProjectStore(root=tmp_path / "projects")
    api = TestClient(
        create_app(TOKEN, allow_test_host=True, project_store=store)
    )
    return store, api


def _new_project(
    api: TestClient,
    *,
    network: str = "TRI",
    voltage_v: str = "400",
    voltage_ln_v: str = "230",
) -> dict[str, Any]:
    response = api.post(
        "/api/project/new",
        headers=AUTH,
        json={
            "name": "R6 receiver results",
            "reference": "R6-RESULTS",
            "client": "",
            "site": "",
            "address": "",
            "author": "Qualification",
            "description": "",
            "observations": "",
            "revision": "A",
            "standard": "NF C 15-100",
            "network": network,
            "voltage_v": voltage_v,
            "has_neutral": True,
            "voltage_ln_v": voltage_ln_v,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _revision(api: TestClient) -> int:
    response = api.get("/api/project", headers=AUTH)
    assert response.status_code == 200, response.text
    return int(response.json()["state"]["revision"])


def _new_feeder(
    api: TestClient,
    *,
    ks: str = "1",
    voltage_ln_v: str = "230",
    parent_board_id: str = "TGBT-01",
    designation: str = "R6 feeder",
) -> str:
    response = api.post(
        "/api/project/feeders",
        headers=AUTH,
        json={
            "expected_revision": _revision(api),
            "parent_board_id": parent_board_id,
            "designation": designation,
            "ks": ks,
            "has_neutral": True,
            "voltage_ln_v": voltage_ln_v,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return next(
        item["id"] for item in payload["feeders"] if item["designation"] == designation
    )


def _add_load(
    api: TestClient,
    feeder_id: str,
    *,
    designation: str,
    network: str,
    voltage_v: str,
    phase: str | None,
    quantity: int = 1,
    nominal_power: str = "1200",
    power_factor: str = "0.92",
    ku: str = "1",
) -> dict[str, Any]:
    response = api.post(
        "/api/project/loads",
        headers=AUTH,
        json={
            "expected_revision": _revision(api),
            "feeder_id": feeder_id,
            "designation": designation,
            "network": network,
            "voltage_v": voltage_v,
            "nominal_power": nominal_power,
            "power_unit": "W",
            "quantity": quantity,
            "power_factor": power_factor,
            "ku": ku,
            "phase": phase,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _load(api: TestClient, designation: str) -> dict[str, Any]:
    payload = api.get("/api/project", headers=AUTH)
    assert payload.status_code == 200, payload.text
    return next(
        item
        for item in payload.json()["loads"]
        if item["designation"] == designation
    )


def _engine_contributions(store: CommandProjectStore) -> dict[str, dict[str, Any]]:
    """Read the engine's total individual P/Q/S/I contributions."""
    from calcelect.service_v11 import calculate_project_v11

    assert store.project is not None
    result = calculate_project_v11(store.project.electrical)
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
                values[contribution.load_id] = {
                    "p_after_ku_w": contribution.p_used_after_w,
                    "q_after_ku_var": contribution.q_used_after_var,
                    "p_after_ks_w": contribution.p_used_after_w,
                    "q_after_ks_var": contribution.q_used_after_var,
                    "s_after_ks_va": contribution.s_used_after_va,
                    "current_a": contribution.current_after_a,
                }
    return values


def _assert_matches_engine(
    store: CommandProjectStore, load: dict[str, Any]
) -> None:
    contributions = _engine_contributions(store)
    expected = contributions[load["id"]]
    for field, value in expected.items():
        assert load[field] == _text(value), field
    assert load["apparent_power_available"] is True
    assert load["current_available"] is True


def test_individual_s_i_match_engine_for_mono_tri_and_historical_network(
    tmp_path: Path,
) -> None:
    cases = (
        ("TRI", "400", "230", "MONO", "230", "L1"),
        ("TRI", "400", "230", "TRI", "400", None),
        ("TRI", "380", "220", "MONO", "220", "L3"),
    )
    for project_network, project_voltage, project_phase_voltage, network, voltage, phase in cases:
        store, api = _client(tmp_path / f"{network}-{project_voltage}")
        try:
            _new_project(
                api,
                network=project_network,
                voltage_v=project_voltage,
                voltage_ln_v=project_phase_voltage,
            )
            feeder_id = _new_feeder(
                api, ks="0.9", voltage_ln_v=project_phase_voltage
            )
            _add_load(
                api,
                feeder_id,
                designation=f"Receiver {network} {voltage}",
                network=network,
                voltage_v=voltage,
                phase=phase,
                quantity=2,
                ku="0.8",
            )
            load = _load(api, f"Receiver {network} {voltage}")
            _assert_matches_engine(store, load)
            assert load["phase"] == phase
            assert load["quantity"] == 2
            assert load["ku"] == "0.8"
            assert load["ks"] == "0.9"
        finally:
            api.close()


def test_mono_phase_l1_l2_l3_each_exposes_individual_s_i(tmp_path: Path) -> None:
    store, api = _client(tmp_path)
    try:
        _new_project(api)
        feeder_id = _new_feeder(api, ks="0.9")
        for phase in ("L1", "L2", "L3"):
            _add_load(
                api,
                feeder_id,
                designation=f"Receiver {phase}",
                network="MONO",
                voltage_v="230",
                phase=phase,
                quantity=2,
                ku="0.8",
            )
        for phase in ("L1", "L2", "L3"):
            load = _load(api, f"Receiver {phase}")
            assert load["phase"] == phase
            _assert_matches_engine(store, load)
            assert load["s_after_ks_va"] is not None
            assert load["current_a"] is not None
    finally:
        api.close()


def test_individual_s_i_are_absent_when_no_calculation_result(tmp_path: Path) -> None:
    store, api = _client(tmp_path)
    try:
        _new_project(api)
        feeder_id = _new_feeder(api)
        _add_load(
            api,
            feeder_id,
            designation="Receiver unavailable",
            network="MONO",
            voltage_v="230",
            phase="L1",
        )
        assert store.project is not None
        payload = build_project_payload(
            store.project.electrical,
            None,
            web={},
            state={},
        )
        load = payload["loads"][0]
        assert load["s_after_ks_va"] is None
        assert load["current_a"] is None
        assert load["apparent_power_available"] is False
        assert load["current_available"] is False
    finally:
        api.close()


def test_multiple_boards_and_feeders_keep_total_receiver_results(tmp_path: Path) -> None:
    store, api = _client(tmp_path)
    try:
        _new_project(api)
        board = api.post(
            "/api/project/boards",
            headers=AUTH,
            json={
                "expected_revision": _revision(api),
                "parent_board_id": "TGBT-01",
                "designation": "R6 board 2",
                "description": "",
                "has_neutral": True,
                "voltage_ln_v": "230",
            },
        )
        assert board.status_code == 200, board.text
        board_id = next(
            item["id"]
            for item in board.json()["boards"]
            if item["designation"] == "R6 board 2"
        )
        feeder_a = _new_feeder(api, parent_board_id="TGBT-01", designation="R6 feeder A")
        feeder_b = _new_feeder(api, parent_board_id=board_id, designation="R6 feeder B")
        _add_load(
            api,
            feeder_a,
            designation="Receiver feeder A",
            network="MONO",
            voltage_v="230",
            phase="L1",
        )
        _add_load(
            api,
            feeder_b,
            designation="Receiver feeder B",
            network="TRI",
            voltage_v="400",
            phase=None,
        )
        payload = api.get("/api/project", headers=AUTH).json()
        assert payload["project"]["board_count"] == 2
        assert payload["project"]["feeder_count"] >= 2
        assert len(payload["loads"]) == 2
        for load in payload["loads"]:
            _assert_matches_engine(store, load)
    finally:
        api.close()


def test_zero_individual_values_are_available_not_unavailable(tmp_path: Path) -> None:
    store, api = _client(tmp_path)
    try:
        _new_project(api)
        feeder_id = _new_feeder(api)
        _add_load(
            api,
            feeder_id,
            designation="Receiver zero",
            network="MONO",
            voltage_v="230",
            phase="L1",
        )
        assert store.project is not None
        assignment = store.project.electrical.loads[0]
        feeder = next(
            item
            for item in store.project.electrical.feeders
            if item.feeder_id == assignment.feeder_id
        )
        payload = _load_payload(
            assignment,
            feeder,
            None,
            "OK",
            [],
            {
                "s_after_ks_va": Decimal(0),
                "current_a": Decimal(0),
            },
        )
        assert payload["s_after_ks_va"] == "0"
        assert payload["current_a"] == "0"
        assert payload["apparent_power_available"] is True
        assert payload["current_available"] is True
    finally:
        api.close()


def test_individual_s_i_survive_save_close_and_reopen(tmp_path: Path) -> None:
    store, api = _client(tmp_path)
    try:
        _new_project(api)
        feeder_id = _new_feeder(api, ks="0.9")
        _add_load(
            api,
            feeder_id,
            designation="Receiver persisted",
            network="MONO",
            voltage_v="230",
            phase="L2",
            quantity=2,
            ku="0.8",
        )
        before = _load(api, "Receiver persisted")
        before_s = before["s_after_ks_va"]
        before_i = before["current_a"]
        target = store.root / "r6-results.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save",
            headers=AUTH,
            json={"path": str(target), "overwrite": False},
        )
        assert saved.status_code == 200, saved.text
        assert api.post("/api/project/close", headers=AUTH).status_code == 200
        reopened = api.post(
            "/api/project/open", headers=AUTH, json={"path": str(target)}
        )
        assert reopened.status_code == 200, reopened.text
        after = next(
            item
            for item in reopened.json()["loads"]
            if item["designation"] == "Receiver persisted"
        )
        assert after["s_after_ks_va"] == before_s
        assert after["current_a"] == before_i
        assert after["apparent_power_available"] is True
        assert after["current_available"] is True
        _assert_matches_engine(store, after)
    finally:
        api.close()
