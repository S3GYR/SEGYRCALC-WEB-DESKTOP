from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.project_commands import CommandProjectStore

TOKEN = "web08-lot3-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def make_api(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            TOKEN,
            allow_test_host=True,
            project_store=CommandProjectStore(root=tmp_path / "projects"),
        )
    )


def project_payload(
    *,
    network: str = "TRI",
    voltage_v: str = "400",
    has_neutral: bool = True,
    voltage_ln_v: str | None = "230",
) -> dict[str, object]:
    return {
        "name": "Projet distribution",
        "reference": "WEB08-LOT3",
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
    }


def create_project(api: TestClient, **kwargs: Any) -> dict:
    response = api.post("/api/project/new", headers=AUTH, json=project_payload(**kwargs))
    assert response.status_code == 200, response.text
    return response.json()


def add_feeder(
    api: TestClient, revision: int, distribution_type: str, phase: str | None = None
) -> tuple[int, dict]:
    response = api.post(
        "/api/project/feeders",
        headers=AUTH,
        json={
            "expected_revision": revision,
            "parent_board_id": "TGBT-01",
            "designation": f"Départ {distribution_type}",
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
    network: str = "TRI",
    voltage_v: str = "400",
    phase: str | None = None,
) -> tuple[int, dict]:
    response = api.post(
        "/api/project/loads",
        headers=AUTH,
        json={
            "expected_revision": revision,
            "feeder_id": feeder_id,
            "designation": "Récepteur",
            "network": network,
            "voltage_v": voltage_v,
            "nominal_power": "2000",
            "power_unit": "W",
            "quantity": 1,
            "power_factor": "0.9",
            "ku": "1",
            "phase": phase,
        },
    )
    return response.status_code, response.json()


def test_mono_l1_l2_l3_distribution(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        for phase in ("L1", "L2", "L3"):
            project = create_project(api)
            revision = project["state"]["revision"]
            status, payload = add_feeder(api, revision, "MONO_N", phase)
            assert status == 200, payload
            feeder = payload["feeders"][-1]
            assert feeder["network"] == "MONO"
            assert feeder["voltage_v"] == "230"
            assert feeder["has_neutral"] is True
            assert feeder["phase"] == phase
            assert feeder["distribution_type"] == "MONO_N"
            status, load_payload = add_load(
                api,
                payload["state"]["revision"],
                feeder["id"],
                network="MONO",
                voltage_v="230",
                phase=phase,
            )
            assert status == 200, load_payload
            assert load_payload["loads"][-1]["phase"] == phase


def test_tri_no_neutral_and_tri_with_neutral(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        revision = project["state"]["revision"]
        status, payload = add_feeder(api, revision, "TRI_NO_N")
        assert status == 200, payload
        feeder = payload["feeders"][-1]
        assert feeder["network"] == "TRI"
        assert feeder["voltage_v"] == "400"
        assert feeder["has_neutral"] is False
        assert feeder["phase"] is None
        assert feeder["distribution_type"] == "TRI_NO_N"
        status, load_payload = add_load(api, payload["state"]["revision"], feeder["id"])
        assert status == 200, load_payload

        status, payload = add_feeder(api, load_payload["state"]["revision"], "TRI_N")
        assert status == 200, payload
        feeder = payload["feeders"][-1]
        assert feeder["network"] == "TRI"
        assert feeder["voltage_v"] == "400"
        assert feeder["voltage_ln_v"] == "230"
        assert feeder["has_neutral"] is True
        assert feeder["phase"] is None
        assert feeder["distribution_type"] == "TRI_N"
        status, load_payload = add_load(api, payload["state"]["revision"], feeder["id"])
        assert status == 200, load_payload
        status, load_payload = add_load(
            api,
            load_payload["state"]["revision"],
            feeder["id"],
            network="MONO",
            voltage_v="230",
            phase="L2",
        )
        assert status == 200, load_payload
        assert load_payload["loads"][-1]["phase"] == "L2"
        assert load_payload["is_calculable"] is True
        assert load_payload["totals"]["s_after_ks_va"] is not None
        assert load_payload["totals"]["current_phases"]["l1"] is not None


def test_parent_compatibility_and_invalid_phase(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api, network="TRI", has_neutral=False, voltage_ln_v=None)
        revision = project["state"]["revision"]
        status, payload = add_feeder(api, revision, "MONO_N", "L1")
        assert status == 422
        assert payload["code"] in {"NEUTRE_ABSENT", "DISTRIBUTION_INCOMPATIBLE"}
        status, payload = add_feeder(api, revision, "TRI_N")
        assert status == 422
        status, payload = add_feeder(api, revision, "TRI_NO_N")
        assert status == 200, payload

        project = create_project(
            api, network="MONO", voltage_v="230", has_neutral=True, voltage_ln_v="230"
        )
        revision = project["state"]["revision"]
        status, payload = add_feeder(api, revision, "TRI_NO_N")
        assert status == 422
        status, payload = add_feeder(api, revision, "MONO_N", "L1")
        assert status == 200, payload


def test_phase_required_and_rejected_on_tri(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        revision = project["state"]["revision"]
        status, payload = add_feeder(api, revision, "MONO_N")
        assert status == 422
        assert payload["code"] == "PHASE_REQUISE"
        status, payload = add_feeder(api, revision, "TRI_N", "L1")
        assert status == 422
        assert payload["code"] == "PHASE_INVALIDE"


def test_distribution_update_is_atomic_and_rejects_incompatible_loads(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        status, payload = add_feeder(api, project["state"]["revision"], "TRI_N")
        assert status == 200, payload
        feeder = payload["feeders"][-1]
        status, payload = add_load(
            api,
            payload["state"]["revision"],
            feeder["id"],
            network="MONO",
            voltage_v="230",
            phase="L1",
        )
        assert status == 200, payload
        revision = payload["state"]["revision"]
        failed = api.put(
            f"/api/project/feeders/{feeder['id']}",
            headers=AUTH,
            json={
                "expected_revision": revision,
                "designation": feeder["designation"],
                "description": "",
                "ks": "0.9",
                "distribution_type": "TRI_NO_N",
                "phase": None,
            },
        )
        assert failed.status_code == 422, failed.text
        current = api.get("/api/project", headers=AUTH).json()
        assert current["state"]["revision"] == revision
        assert (
            next(item for item in current["feeders"] if item["id"] == feeder["id"])["has_neutral"]
            is True
        )


def test_mono_phase_change_propagates_atomically(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        status, payload = add_feeder(api, project["state"]["revision"], "MONO_N", "L1")
        assert status == 200, payload
        feeder = payload["feeders"][-1]
        status, payload = add_load(
            api,
            payload["state"]["revision"],
            feeder["id"],
            network="MONO",
            voltage_v="230",
            phase="L1",
        )
        assert status == 200, payload
        changed = api.put(
            f"/api/project/feeders/{feeder['id']}",
            headers=AUTH,
            json={
                "expected_revision": payload["state"]["revision"],
                "designation": feeder["designation"],
                "description": "",
                "ks": "0.9",
                "distribution_type": "MONO_N",
                "phase": "L3",
            },
        )
        assert changed.status_code == 200, changed.text
        changed_payload = changed.json()
        assert (
            next(item for item in changed_payload["feeders"] if item["id"] == feeder["id"])["phase"]
            == "L3"
        )
        assert (
            next(item for item in changed_payload["loads"] if item["feeder_id"] == feeder["id"])[
                "phase"
            ]
            == "L3"
        )
        assert changed_payload["state"]["revision"] == payload["state"]["revision"] + 1

        undone = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": changed_payload["state"]["revision"]},
        )
        assert undone.status_code == 200, undone.text
        assert (
            next(item for item in undone.json()["feeders"] if item["id"] == feeder["id"])["phase"]
            == "L1"
        )
        redone = api.post(
            "/api/project/redo",
            headers=AUTH,
            json={"expected_revision": undone.json()["state"]["revision"]},
        )
        assert redone.status_code == 200, redone.text
        assert (
            next(item for item in redone.json()["feeders"] if item["id"] == feeder["id"])["phase"]
            == "L3"
        )


def test_non_standard_voltages_are_preserved(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(
            api,
            network="TRI",
            voltage_v="380",
            has_neutral=True,
            voltage_ln_v="220",
        )
        status, payload = add_feeder(api, project["state"]["revision"], "MONO_N", "L1")
        assert status == 200, payload
        mono = payload["feeders"][-1]
        assert mono["voltage_v"] == "220"
        assert mono["voltage_ln_v"] == "220"

        status, payload = add_feeder(api, payload["state"]["revision"], "TRI_N")
        assert status == 200, payload
        tri = payload["feeders"][-1]
        assert tri["voltage_v"] == "380"
        assert tri["voltage_ln_v"] == "220"


def test_distribution_type_is_not_persisted(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        status, payload = add_feeder(api, project["state"]["revision"], "TRI_N")
        assert status == 200, payload
        target = tmp_path / "projects" / "distribution-persist.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save", headers=AUTH, json={"path": str(target), "overwrite": False}
        )
        assert saved.status_code == 200, saved.text
        text = target.read_text(encoding="utf-8")
        assert "distribution_type" not in text
        assert '"has_neutral": true' in text
        assert '"voltage_ln_v": "230"' in text


def test_board_feeder_distribution_cannot_diverge_from_child(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        board_response = api.post(
            "/api/project/boards",
            headers=AUTH,
            json={
                "expected_revision": project["state"]["revision"],
                "parent_board_id": "TGBT-01",
                "designation": "Tableau aval",
                "description": "Test",
                "has_neutral": True,
                "voltage_ln_v": "230",
            },
        )
        assert board_response.status_code == 200, board_response.text
        board_payload = board_response.json()
        board = next(item for item in board_payload["boards"] if item["type"] == "DIVISIONNAIRE")
        feeder = next(
            item for item in board_payload["feeders"] if item["downstream_board_id"] == board["id"]
        )
        failed = api.put(
            f"/api/project/feeders/{feeder['id']}",
            headers=AUTH,
            json={
                "expected_revision": board_payload["state"]["revision"],
                "designation": feeder["designation"],
                "description": "",
                "ks": None,
                "distribution_type": "TRI_NO_N",
                "phase": None,
            },
        )
        assert failed.status_code == 422, failed.text
        current = api.get("/api/project", headers=AUTH).json()
        current_feeder = next(item for item in current["feeders"] if item["id"] == feeder["id"])
        assert current_feeder["has_neutral"] is True
        assert current["state"]["revision"] == board_payload["state"]["revision"]


def test_save_reopen_preserves_distribution(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        status, payload = add_feeder(api, project["state"]["revision"], "TRI_N")
        assert status == 200, payload
        target = tmp_path / "projects" / "distribution.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save", headers=AUTH, json={"path": str(target), "overwrite": False}
        )
        assert saved.status_code == 200, saved.text
        api.post("/api/project/close", headers=AUTH)
        reopened = api.post("/api/project/open", headers=AUTH, json={"path": str(target)})
        assert reopened.status_code == 200, reopened.text
        feeder = reopened.json()["feeders"][-1]
        assert feeder["distribution_type"] == "TRI_N"
        assert feeder["has_neutral"] is True
        assert feeder["phase"] is None
        assert feeder["voltage_ln_v"] == "230"
