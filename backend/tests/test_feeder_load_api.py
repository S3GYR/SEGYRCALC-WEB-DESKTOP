from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.project_commands import CommandProjectStore

TOKEN = "lot2-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def make_api(tmp_path: Path) -> TestClient:
    store = CommandProjectStore(root=tmp_path / "projects")
    return TestClient(create_app(TOKEN, allow_test_host=True, project_store=store))


def new_project(
    api: TestClient,
    *,
    voltage: str = "400",
    voltage_ln: str = "230",
    has_neutral: bool = True,
) -> dict[str, Any]:
    response = api.post(
        "/api/project/new",
        headers=AUTH,
        json={
            "name": "Lot 2",
            "reference": "LOT2-TEST",
            "client": "",
            "site": "Site",
            "address": "1 rue du Test",
            "author": "Qualification",
            "description": "",
            "observations": "",
            "revision": "A",
            "standard": "NF C 15-100",
            "network": "TRI",
            "voltage_v": voltage,
            "has_neutral": has_neutral,
            "voltage_ln_v": voltage_ln,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def pair_payload(
    project: dict[str, Any],
    distribution: str,
    *,
    phase: str | None = None,
    load_network: str = "TRI",
    load_voltage: str = "400",
    load_phase: str | None = None,
) -> dict[str, Any]:
    feeder = {
        "designation": f"Départ {distribution}",
        "description": "",
        "distribution_type": distribution,
        "phase": phase,
        "ks": "0.9",
    }
    load = {
        "designation": f"Récepteur {distribution}",
        "network": load_network,
        "voltage_v": load_voltage,
        "nominal_power": "1000",
        "power_unit": "W",
        "quantity": 1,
        "power_factor": "0.9",
        "ku": "0.8",
        "phase": load_phase,
    }
    return {
        "expected_revision": project["state"]["revision"],
        "parent_board_id": project["boards"][0]["id"],
        "feeder": feeder,
        "load": load,
    }


def create_pair(api: TestClient, project: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    response = api.post("/api/project/feeders-with-load", headers=AUTH, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def latest_feeder(project: dict[str, Any]) -> dict[str, Any]:
    return project["feeders"][-1]


def test_mono_n_l1_l2_l3_same_phase() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        with make_api(Path(directory)) as api:
            initial = new_project(api)
            for phase in ("L1", "L2", "L3"):
                project = create_pair(
                    api,
                    initial,
                    pair_payload(
                        initial,
                        "MONO_N",
                        phase=phase,
                        load_network="MONO",
                        load_voltage="230",
                        load_phase=phase,
                    ),
                )
                feeder = latest_feeder(project)
                load = project["loads"][-1]
                assert feeder["phase"] == phase
                assert load["phase"] == phase
                assert load["feeder_id"] == feeder["id"]
                assert load["voltage_v"] == "230"
                initial = project


def test_tri_no_n_and_tri_n() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        with make_api(Path(directory)) as api:
            initial = new_project(api)
            for distribution in ("TRI_NO_N", "TRI_N"):
                project = create_pair(
                    api,
                    initial,
                    pair_payload(
                        initial,
                        distribution,
                        load_network="TRI",
                        load_voltage="400",
                    ),
                )
                feeder = latest_feeder(project)
                assert feeder["distribution_type"] == distribution
                assert feeder["phase"] is None
                assert project["loads"][-1]["phase"] is None
                initial = project


def test_voltages_400_230_and_380_220() -> None:
    import tempfile

    for voltage, voltage_ln in (("400", "230"), ("380", "220")):
        with tempfile.TemporaryDirectory() as directory:
            with make_api(Path(directory)) as api:
                project = new_project(api, voltage=voltage, voltage_ln=voltage_ln)
                project = create_pair(
                    api,
                    project,
                    pair_payload(
                        project,
                        "MONO_N",
                        phase="L1",
                        load_network="MONO",
                        load_voltage=voltage_ln,
                        load_phase="L1",
                    ),
                )
                assert latest_feeder(project)["voltage_v"] == voltage_ln
                assert project["loads"][-1]["voltage_v"] == voltage_ln


def test_validation_and_no_orphan_on_load_failure() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        with make_api(Path(directory)) as api:
            project = new_project(api)
            before_feeders = len(project["feeders"])
            before_loads = len(project["loads"])
            invalid = pair_payload(
                project,
                "MONO_N",
                phase="L1",
                load_network="TRI",
                load_voltage="400",
            )
            response = api.post("/api/project/feeders-with-load", headers=AUTH, json=invalid)
            assert response.status_code == 422
            current = api.get("/api/project", headers=AUTH).json()
            assert len(current["feeders"]) == before_feeders
            assert len(current["loads"]) == before_loads

            missing = pair_payload(project, "TRI_N")
            missing["load"]["designation"] = ""
            response = api.post("/api/project/feeders-with-load", headers=AUTH, json=missing)
            assert response.status_code == 422
            current = api.get("/api/project", headers=AUTH).json()
            assert len(current["feeders"]) == before_feeders
            assert len(current["loads"]) == before_loads


def test_invalid_parent_and_invalid_values() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        with make_api(Path(directory)) as api:
            project = new_project(api)
            payload = pair_payload(project, "TRI_N")
            payload["parent_board_id"] = "UNKNOWN"
            response = api.post("/api/project/feeders-with-load", headers=AUTH, json=payload)
            assert response.status_code == 404

            payload = pair_payload(project, "TRI_N")
            payload["load"]["nominal_power"] = "0"
            response = api.post("/api/project/feeders-with-load", headers=AUTH, json=payload)
            assert response.status_code == 422

            no_neutral = new_project(api, has_neutral=False)
            payload = pair_payload(no_neutral, "MONO_N", phase="L1", load_network="MONO")
            response = api.post("/api/project/feeders-with-load", headers=AUTH, json=payload)
            assert response.status_code == 422
            current = api.get("/api/project", headers=AUTH).json()
            assert len(current["feeders"]) == len(no_neutral["feeders"])
            assert len(current["loads"]) == len(no_neutral["loads"])


def test_tri_n_accepts_mono_receiver_with_explicit_phase(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        project = create_pair(
            api,
            project,
            pair_payload(
                project,
                "TRI_N",
                load_network="MONO",
                load_voltage="230",
                load_phase="L2",
            ),
        )
        feeder = latest_feeder(project)
        load = project["loads"][-1]
        assert feeder["network"] == "TRI"
        assert feeder["has_neutral"] is True
        assert feeder["phase"] is None
        assert load["network"] == "MONO"
        assert load["phase"] == "L2"
        assert load["feeder_id"] == feeder["id"]
        assert project["coherence"]["orphan_load_ids"] == []


def test_undo_and_redo_are_single_and_preserve_ids(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        payload = pair_payload(
            project,
            "MONO_N",
            phase="L2",
            load_network="MONO",
            load_voltage="230",
            load_phase="L2",
        )
        history_before = project["state"]["undo_depth"]
        project = create_pair(api, project, payload)
        feeder_id = project["feeders"][-1]["id"]
        load_id = project["loads"][-1]["id"]
        assert project["state"]["undo_depth"] == history_before + 1
        undone = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": project["state"]["revision"]},
        )
        assert undone.status_code == 200, undone.text
        assert all(item["id"] != feeder_id for item in undone.json()["feeders"])
        assert all(item["id"] != load_id for item in undone.json()["loads"])
        redone = api.post(
            "/api/project/redo",
            headers=AUTH,
            json={"expected_revision": undone.json()["state"]["revision"]},
        )
        assert redone.status_code == 200, redone.text
        assert any(item["id"] == feeder_id for item in redone.json()["feeders"])
        assert any(item["id"] == load_id for item in redone.json()["loads"])
        assert redone.json()["loads"][-1]["feeder_id"] == feeder_id


def test_revision_conflict_and_required_feeder_designation_do_not_mutate(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        response = api.post(
            "/api/project/feeders-with-load",
            headers=AUTH,
            json={**pair_payload(project, "TRI_N"), "expected_revision": project["state"]["revision"] + 1},
        )
        assert response.status_code in (409, 422), response.text
        current = api.get("/api/project", headers=AUTH).json()
        assert current["feeders"] == project["feeders"]
        assert current["loads"] == project["loads"]

        missing = pair_payload(project, "TRI_N")
        missing["feeder"]["designation"] = ""
        response = api.post("/api/project/feeders-with-load", headers=AUTH, json=missing)
        assert response.status_code == 422
        current = api.get("/api/project", headers=AUTH).json()
        assert current["state"]["revision"] == project["state"]["revision"]
        assert len(current["feeders"]) == len(project["feeders"])
        assert len(current["loads"]) == len(project["loads"])


def test_undo_depth_and_redo_restore_single_history_entry(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        project = create_pair(
            api,
            project,
            pair_payload(project, "TRI_NO_N", phase=None),
        )
        assert project["state"]["undo_depth"] == 1
        assert project["state"]["can_undo"] is True
        undone = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": project["state"]["revision"]},
        )
        assert undone.status_code == 200, undone.text
        assert undone.json()["state"]["undo_depth"] == 0
        assert undone.json()["state"]["redo_depth"] == 1
        redone = api.post(
            "/api/project/redo",
            headers=AUTH,
            json={"expected_revision": undone.json()["state"]["revision"]},
        )
        assert redone.status_code == 200, redone.text
        assert redone.json()["state"]["undo_depth"] == 1
        assert redone.json()["state"]["redo_depth"] == 0


def test_save_reopen_and_recalculation(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        project = create_pair(
            api,
            project,
            pair_payload(
                project,
                "MONO_N",
                phase="L3",
                load_network="MONO",
                load_voltage="230",
                load_phase="L3",
            ),
        )
        assert project["totals"]["p_installed_w"] is not None
        target = tmp_path / "projects" / "lot2.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save",
            headers=AUTH,
            json={"path": str(target), "overwrite": True},
        )
        assert saved.status_code == 200, saved.text
        feeder_id = project["feeders"][-1]["id"]
        load_id = project["loads"][-1]["id"]
        reopened = api.post("/api/project/open", headers=AUTH, json={"path": str(target)})
        assert reopened.status_code == 200, reopened.text
        assert any(item["id"] == feeder_id for item in reopened.json()["feeders"])
        assert any(item["id"] == load_id for item in reopened.json()["loads"])


def test_unified_pair_designations_then_independent_edits_and_second_load(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        payload = pair_payload(project, "TRI_N")
        payload["feeder"]["designation"] = "Éclairage"
        payload["load"]["designation"] = "Éclairage"
        project = create_pair(api, project, payload)
        feeder = latest_feeder(project)
        first_load = project["loads"][-1]
        assert feeder["designation"] == "Éclairage"
        assert first_load["designation"] == "Éclairage"
        assert first_load["feeder_id"] == feeder["id"]

        feeder_update = api.put(
            f"/api/project/feeders/{feeder['id']}",
            headers=AUTH,
            json={
                "expected_revision": project["state"]["revision"],
                "designation": "Départ Éclairage",
                "description": "",
                "ks": "0.9",
                "distribution_type": "TRI_N",
                "phase": None,
            },
        )
        assert feeder_update.status_code == 200, feeder_update.text
        project = feeder_update.json()

        load_update = api.put(
            f"/api/project/loads/{first_load['id']}",
            headers=AUTH,
            json={
                "expected_revision": project["state"]["revision"],
                "designation": "Récepteur Éclairage",
                "network": first_load["network"],
                "voltage_v": first_load["voltage_v"],
                "nominal_power": first_load["nominal_power"],
                "power_unit": first_load["power_unit"],
                "quantity": first_load["quantity"],
                "power_factor": first_load["power_factor"],
                "ku": first_load["ku"],
                "phase": first_load["phase"],
            },
        )
        assert load_update.status_code == 200, load_update.text
        project = load_update.json()
        assert next(item for item in project["feeders"] if item["id"] == feeder["id"])["designation"] == "Départ Éclairage"
        assert next(item for item in project["loads"] if item["id"] == first_load["id"])["designation"] == "Récepteur Éclairage"

        second = api.post(
            "/api/project/loads",
            headers=AUTH,
            json={
                "expected_revision": project["state"]["revision"],
                "feeder_id": feeder["id"],
                "designation": "Deuxième r?cepteur",
                "network": "TRI",
                "voltage_v": "400",
                "nominal_power": "500",
                "power_unit": "W",
                "quantity": 1,
                "power_factor": "0.9",
                "ku": "1",
                "phase": None,
            },
        )
        assert second.status_code == 200, second.text
        assert second.json()["project"]["load_count"] == 2
        assert second.json()["coherence"]["orphan_load_ids"] == []
