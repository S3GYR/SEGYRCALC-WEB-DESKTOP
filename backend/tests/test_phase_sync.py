from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.project_commands import CommandProjectStore

TOKEN = "web08-lot3-phase-sync-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def make_api(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            TOKEN,
            allow_test_host=True,
            project_store=CommandProjectStore(root=tmp_path / "projects"),
        )
    )


def create_project(
    api: TestClient,
    *,
    network: str = "TRI",
    voltage_v: str = "400",
    has_neutral: bool = True,
    voltage_ln_v: str | None = "230",
) -> dict[str, Any]:
    response = api.post(
        "/api/project/new",
        headers=AUTH,
        json={
            "name": "Projet phases",
            "reference": "WEB08-LOT3-PHASES",
            "client": "",
            "site": "Site",
            "address": "1 rue du Site",
            "author": "Qualification",
            "description": "",
            "observations": "",
            "revision": "A",
            "standard": "NF C 15-100",
            "network": network,
            "voltage_v": voltage_v,
            "has_neutral": has_neutral,
            "voltage_ln_v": voltage_ln_v,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_feeder(
    api: TestClient,
    revision: int,
    distribution_type: str,
    phase: str | None = None,
    designation: str = "Départ phases",
) -> tuple[int, dict[str, Any]]:
    response = api.post(
        "/api/project/feeders",
        headers=AUTH,
        json={
            "expected_revision": revision,
            "parent_board_id": "TGBT-01",
            "designation": designation,
            "description": "",
            "ks": "0.9",
            "distribution_type": distribution_type,
            "phase": phase,
        },
    )
    return response.status_code, response.json()


def add_load(
    api: TestClient,
    revision: int,
    feeder_id: str,
    *,
    designation: str = "Récepteur phases",
    network: str = "MONO",
    voltage_v: str = "230",
    phase: str | None = None,
    include_phase: bool = True,
) -> tuple[int, dict[str, Any]]:
    body: dict[str, Any] = {
        "expected_revision": revision,
        "feeder_id": feeder_id,
        "designation": designation,
        "network": network,
        "voltage_v": voltage_v,
        "nominal_power": "1000",
        "power_unit": "W",
        "quantity": 1,
        "power_factor": "0.9",
        "ku": "1",
    }
    if include_phase:
        body["phase"] = phase
    response = api.post("/api/project/loads", headers=AUTH, json=body)
    return response.status_code, response.json()


def update_load(
    api: TestClient,
    revision: int,
    load: dict[str, Any],
    *,
    phase: str | None,
    designation: str | None = None,
) -> tuple[int, dict[str, Any]]:
    response = api.put(
        f"/api/project/loads/{load['id']}",
        headers=AUTH,
        json={
            "expected_revision": revision,
            "feeder_id": load["feeder_id"],
            "designation": designation or load["designation"],
            "network": load["network"],
            "voltage_v": load["voltage_v"],
            "nominal_power": load["nominal_power"],
            "power_unit": load["power_unit"],
            "quantity": load["quantity"],
            "power_factor": load["power_factor"],
            "ku": load["ku"],
            "phase": phase,
        },
    )
    return response.status_code, response.json()


def test_creation_inherits_monophase_phase_l1_l2_l3(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        for phase, voltage in (("L1", "230"), ("L2", "230"), ("L3", "230")):
            project = create_project(api)
            status, feeder_payload = create_feeder(
                api, project["state"]["revision"], "MONO_N", phase, f"Départ {phase}"
            )
            assert status == 200, feeder_payload
            feeder = feeder_payload["feeders"][-1]
            status, load_payload = add_load(
                api,
                feeder_payload["state"]["revision"],
                feeder["id"],
                include_phase=False,
                voltage_v=voltage,
            )
            assert status == 200, load_payload
            created = load_payload["loads"][-1]
            assert created["phase"] == phase
            assert created["voltage_v"] == voltage
            assert created["feeder_id"] == feeder["id"]


def test_creation_rejects_phase_different_from_monophase_feeder(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        status, feeder_payload = create_feeder(api, project["state"]["revision"], "MONO_N", "L1")
        assert status == 200, feeder_payload
        feeder = feeder_payload["feeders"][-1]
        revision = feeder_payload["state"]["revision"]
        status, payload = add_load(
            api,
            revision,
            feeder["id"],
            phase="L2",
        )
        assert status == 422, payload
        assert payload["code"] == "PHASE_INCOMPATIBLE"
        current = api.get("/api/project", headers=AUTH).json()
        assert current["state"]["revision"] == revision
        assert not [item for item in current["loads"] if item["designation"] == "Récepteur phases"]


def test_receiver_phase_change_moves_feeder_and_all_receivers_atomically(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        status, feeder_payload = create_feeder(api, project["state"]["revision"], "MONO_N", "L1")
        assert status == 200, feeder_payload
        feeder = feeder_payload["feeders"][-1]
        revision = feeder_payload["state"]["revision"]
        load_ids: list[str] = []
        for index in range(3):
            status, load_payload = add_load(
                api,
                revision,
                feeder["id"],
                designation=f"Récepteur {index + 1}",
            )
            assert status == 200, load_payload
            revision = load_payload["state"]["revision"]
            load_ids.append(load_payload["loads"][-1]["id"])

        first = next(item for item in load_payload["loads"] if item["id"] == load_ids[0])
        status, changed = update_load(api, revision, first, phase="L3")
        assert status == 200, changed
        changed_revision = changed["state"]["revision"]
        assert changed_revision == revision + 1
        changed_feeder = next(item for item in changed["feeders"] if item["id"] == feeder["id"])
        assert changed_feeder["phase"] == "L3"
        for load_id in load_ids:
            assert next(item for item in changed["loads"] if item["id"] == load_id)["phase"] == "L3"

        undone = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": changed_revision},
        )
        assert undone.status_code == 200, undone.text
        undone_payload = undone.json()
        assert (
            next(item for item in undone_payload["feeders"] if item["id"] == feeder["id"])["phase"]
            == "L1"
        )
        for load_id in load_ids:
            assert (
                next(item for item in undone_payload["loads"] if item["id"] == load_id)["phase"]
                == "L1"
            )

        redone = api.post(
            "/api/project/redo",
            headers=AUTH,
            json={"expected_revision": undone_payload["state"]["revision"]},
        )
        assert redone.status_code == 200, redone.text
        assert (
            next(item for item in redone.json()["feeders"] if item["id"] == feeder["id"])["phase"]
            == "L3"
        )


def test_feeder_phase_change_propagates_to_all_receivers(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        status, feeder_payload = create_feeder(api, project["state"]["revision"], "MONO_N", "L2")
        assert status == 200, feeder_payload
        feeder = feeder_payload["feeders"][-1]
        revision = feeder_payload["state"]["revision"]
        for index in range(2):
            status, load_payload = add_load(
                api,
                revision,
                feeder["id"],
                designation=f"Récepteur {index + 1}",
            )
            assert status == 200, load_payload
            revision = load_payload["state"]["revision"]

        changed = api.put(
            f"/api/project/feeders/{feeder['id']}",
            headers=AUTH,
            json={
                "expected_revision": revision,
                "designation": feeder["designation"],
                "description": "",
                "ks": "0.9",
                "distribution_type": "MONO_N",
                "phase": "L1",
            },
        )
        assert changed.status_code == 200, changed.text
        changed_payload = changed.json()
        assert (
            next(item for item in changed_payload["feeders"] if item["id"] == feeder["id"])["phase"]
            == "L1"
        )
        assert {
            item["phase"] for item in changed_payload["loads"] if item["feeder_id"] == feeder["id"]
        } == {"L1"}
        assert changed_payload["state"]["revision"] == revision + 1


def test_tri_n_receiver_phase_change_is_independent_and_recalculates(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        status, feeder_payload = create_feeder(api, project["state"]["revision"], "TRI_N")
        assert status == 200, feeder_payload
        feeder = feeder_payload["feeders"][-1]
        revision = feeder_payload["state"]["revision"]
        load_ids: list[str] = []
        for phase in ("L1", "L2", "L3"):
            status, load_payload = add_load(
                api,
                revision,
                feeder["id"],
                designation=f"Récepteur {phase}",
                phase=phase,
            )
            assert status == 200, load_payload
            revision = load_payload["state"]["revision"]
            load_ids.append(load_payload["loads"][-1]["id"])

        target = next(item for item in load_payload["loads"] if item["id"] == load_ids[0])
        status, changed = update_load(api, revision, target, phase="L2")
        assert status == 200, changed
        changed_feeder = next(item for item in changed["feeders"] if item["id"] == feeder["id"])
        assert changed_feeder["phase"] is None
        assert changed_feeder["distribution_type"] == "TRI_N"
        phases = {
            item["id"]: item["phase"]
            for item in changed["loads"]
            if item["feeder_id"] == feeder["id"]
        }
        assert phases[load_ids[0]] == "L2"
        assert phases[load_ids[1]] == "L2"
        assert phases[load_ids[2]] == "L3"
        assert changed["state"]["revision"] == revision + 1
        assert changed["is_calculable"] is True
        for phase_key in ("l1", "l2", "l3"):
            assert changed["totals"]["current_phases"][phase_key] is not None
        assert changed["totals"]["neutral_current_a"] is not None


def test_tri_without_neutral_rejects_monophase_and_partial_creation(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(
            api,
            network="TRI",
            voltage_v="400",
            has_neutral=False,
            voltage_ln_v=None,
        )
        status, feeder_payload = create_feeder(api, project["state"]["revision"], "TRI_NO_N")
        assert status == 200, feeder_payload
        feeder = feeder_payload["feeders"][-1]
        revision = feeder_payload["state"]["revision"]
        status, payload = add_load(api, revision, feeder["id"], phase="L1")
        assert status == 422, payload
        assert payload["code"] == "NEUTRE_ABSENT"
        current = api.get("/api/project", headers=AUTH).json()
        assert current["state"]["revision"] == revision
        assert not [item for item in current["loads"] if item["feeder_id"] == feeder["id"]]

        status, payload = add_load(
            api,
            revision,
            feeder["id"],
            network="TRI",
            voltage_v="400",
            phase="L1",
        )
        assert status == 422, payload
        assert payload["code"] == "PHASE_INVALIDE"


def test_invalid_receiver_phase_change_is_atomic(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        status, feeder_payload = create_feeder(api, project["state"]["revision"], "MONO_N", "L1")
        assert status == 200, feeder_payload
        feeder = feeder_payload["feeders"][-1]
        status, load_payload = add_load(api, feeder_payload["state"]["revision"], feeder["id"])
        assert status == 200, load_payload
        revision = load_payload["state"]["revision"]
        target = load_payload["loads"][-1]
        status, changed = update_load(api, revision, target, phase="L4")
        assert status == 422, changed
        assert changed["code"] == "PHASE_INVALIDE"
        current = api.get("/api/project", headers=AUTH).json()
        assert current["state"]["revision"] == revision
        assert (
            next(item for item in current["feeders"] if item["id"] == feeder["id"])["phase"] == "L1"
        )
        assert (
            next(item for item in current["loads"] if item["id"] == target["id"])["phase"] == "L1"
        )


def test_phase_sync_survives_save_and_reopen(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        status, feeder_payload = create_feeder(api, project["state"]["revision"], "MONO_N", "L2")
        assert status == 200, feeder_payload
        feeder = feeder_payload["feeders"][-1]
        status, load_payload = add_load(api, feeder_payload["state"]["revision"], feeder["id"])
        assert status == 200, load_payload
        target = next(
            item for item in load_payload["loads"] if item["id"] == load_payload["loads"][-1]["id"]
        )
        status, changed = update_load(api, load_payload["state"]["revision"], target, phase="L3")
        assert status == 200, changed
        target_path = tmp_path / "projects" / "phase-sync.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save",
            headers=AUTH,
            json={"path": str(target_path), "overwrite": False},
        )
        assert saved.status_code == 200, saved.text
        api.post("/api/project/close", headers=AUTH)
        reopened = api.post("/api/project/open", headers=AUTH, json={"path": str(target_path)})
        assert reopened.status_code == 200, reopened.text
        reopened_payload = reopened.json()
        assert (
            next(item for item in reopened_payload["feeders"] if item["id"] == feeder["id"])[
                "phase"
            ]
            == "L3"
        )
        assert (
            next(item for item in reopened_payload["loads"] if item["id"] == target["id"])["phase"]
            == "L3"
        )
