from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.project_commands import CommandProjectStore

TOKEN = "lot2-reference-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def make_api(tmp_path: Path) -> TestClient:
    store = CommandProjectStore(root=tmp_path / "projects")
    return TestClient(create_app(TOKEN, allow_test_host=True, project_store=store))


def new_project(api: TestClient) -> dict[str, Any]:
    response = api.post(
        "/api/project/new",
        headers=AUTH,
        json={
            "name": "Repères",
            "reference": "REP-TEST",
            "client": "",
            "site": "Site",
            "address": "",
            "author": "Qualification",
            "description": "",
            "observations": "",
            "revision": "A",
            "standard": "NF C 15-100",
            "network": "TRI",
            "voltage_v": "400",
            "has_neutral": True,
            "voltage_ln_v": "230",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def add_board(api: TestClient, project: dict[str, Any], designation: str) -> tuple[dict[str, Any], str]:
    response = api.post(
        "/api/project/boards",
        headers=AUTH,
        json={
            "expected_revision": project["state"]["revision"],
            "parent_board_id": project["boards"][0]["id"],
            "designation": designation,
            "has_neutral": True,
            "voltage_ln_v": "230",
        },
    )
    assert response.status_code == 200, response.text
    board = next(item for item in response.json()["boards"] if item["designation"] == designation)
    return response.json(), board["id"]


def add_feeder(
    api: TestClient,
    project: dict[str, Any],
    board_id: str,
    *,
    reference: str | None = None,
    auto_reference: bool = False,
    designation: str = "Départ test",
) -> dict[str, Any]:
    response = api.post(
        "/api/project/feeders",
        headers=AUTH,
        json={
            "expected_revision": project["state"]["revision"],
            "parent_board_id": board_id,
            "reference": reference,
            "auto_reference": auto_reference,
            "designation": designation,
            "description": "",
            "ks": "0.9",
            "distribution_type": "TRI_N",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def created_feeder(payload: dict[str, Any], board_id: str) -> dict[str, Any]:
    return next(
        feeder
        for feeder in reversed(payload["feeders"])
        if feeder["parent_board_id"] == board_id and feeder["reference"]
    )


def test_empty_board_starts_at_q1_and_sequences(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        board_id = project["boards"][0]["id"]

        project = add_feeder(api, project, board_id, auto_reference=True)
        assert created_feeder(project, board_id)["reference"] == "Q1"

        project = add_feeder(api, project, board_id, auto_reference=True)
        assert created_feeder(project, board_id)["reference"] == "Q2"

        project = add_feeder(api, project, board_id, auto_reference=True)
        assert created_feeder(project, board_id)["reference"] == "Q3"


def test_max_existing_number_is_used(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        board_id = project["boards"][0]["id"]
        project = add_feeder(api, project, board_id, reference="Q1")
        project = add_feeder(api, project, board_id, reference="Q3")
        project = add_feeder(api, project, board_id, auto_reference=True)
        assert created_feeder(project, board_id)["reference"] == "Q4"


def test_custom_reference_and_collision_rules(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        board_id = project["boards"][0]["id"]
        project = add_feeder(api, project, board_id, reference="TD-A")
        assert created_feeder(project, board_id)["reference"] == "TD-A"

        refused = api.post(
            "/api/project/feeders",
            headers=AUTH,
            json={
                "expected_revision": project["state"]["revision"],
                "parent_board_id": board_id,
                "reference": "TD-A",
                "auto_reference": False,
                "designation": "Doublon",
                "description": "",
                "ks": "0.9",
                "distribution_type": "TRI_N",
            },
        )
        assert refused.status_code == 422
        assert refused.json()["code"] == "REPERE_DEPART_DUPLIQUE"
        assert "TD-A" in refused.json()["detail"]


def test_two_boards_are_independent(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        root = project["boards"][0]["id"]
        project, child = add_board(api, project, "TD-01")
        project = add_feeder(api, project, root, auto_reference=True)
        project = add_feeder(api, project, child, auto_reference=True)
        assert created_feeder(project, root)["reference"] == "Q1"
        assert created_feeder(project, child)["reference"] == "Q1"

        project = add_feeder(api, project, child, auto_reference=True)
        assert created_feeder(project, child)["reference"] == "Q2"


def test_two_auto_creations_do_not_duplicate(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        board_id = project["boards"][0]["id"]
        project = add_feeder(api, project, board_id, reference="Q1", auto_reference=True)
        project = add_feeder(api, project, board_id, reference="Q1", auto_reference=True)
        references = [
            feeder["reference"]
            for feeder in project["feeders"]
            if feeder["parent_board_id"] == board_id and feeder["reference"]
        ]
        assert references == ["Q1", "Q2"]


def test_deleted_number_is_not_reused(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        board_id = project["boards"][0]["id"]
        project = add_feeder(api, project, board_id, auto_reference=True)
        project = add_feeder(api, project, board_id, auto_reference=True)
        first_id = next(
            feeder["id"]
            for feeder in project["feeders"]
            if feeder["parent_board_id"] == board_id and feeder["reference"] == "Q1"
        )
        deleted = api.delete(
            f"/api/project/feeders/{first_id}?expected_revision={project['state']['revision']}",
            headers=AUTH,
        )
        assert deleted.status_code == 200, deleted.text
        project = add_feeder(api, deleted.json(), board_id, auto_reference=True)
        assert created_feeder(project, board_id)["reference"] == "Q3"


def test_undo_redo_preserves_references(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        board_id = project["boards"][0]["id"]
        project = add_feeder(api, project, board_id, reference="Q1")
        project = add_feeder(api, project, board_id, reference="Q2")
        undone = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": project["state"]["revision"]},
        )
        assert undone.status_code == 200, undone.text
        assert [item["reference"] for item in undone.json()["feeders"]] == ["Q1"]
        redone = api.post(
            "/api/project/redo",
            headers=AUTH,
            json={"expected_revision": undone.json()["state"]["revision"]},
        )
        assert redone.status_code == 200, redone.text
        assert [item["reference"] for item in redone.json()["feeders"]] == ["Q1", "Q2"]


def test_save_and_reopen_preserve_references(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        board_id = project["boards"][0]["id"]
        project = add_feeder(api, project, board_id, reference="Q1", designation="Éclairage RDC")
        project = add_feeder(api, project, board_id, auto_reference=True)
        target = tmp_path / "projects" / "references.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save",
            headers=AUTH,
            json={"path": str(target), "overwrite": True},
        )
        assert saved.status_code == 200, saved.text
        reopened = api.post("/api/project/open", headers=AUTH, json={"path": str(target)})
        assert reopened.status_code == 200, reopened.text
        feeders = [
            item
            for item in reopened.json()["feeders"]
            if item["parent_board_id"] == board_id
        ]
        assert [(item["reference"], item["designation"]) for item in feeders] == [
            ("Q1", "Éclairage RDC"),
            ("Q2", "Départ test"),
        ]
        reopened_file = target.read_text(encoding="utf-8")
        assert "feeder_references" in reopened_file


def test_atomic_pair_uses_backend_reference(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = new_project(api)
        board_id = project["boards"][0]["id"]
        response = api.post(
            "/api/project/feeders-with-load",
            headers=AUTH,
            json={
                "expected_revision": project["state"]["revision"],
                "parent_board_id": board_id,
                "feeder": {
                    "reference": "Q7",
                    "auto_reference": True,
                    "designation": "CTA",
                    "description": "",
                    "distribution_type": "TRI_N",
                    "phase": None,
                    "ks": "0.9",
                },
                "load": {
                    "designation": "CTA-01",
                    "network": "TRI",
                    "voltage_v": "400",
                    "nominal_power": "1000",
                    "power_unit": "W",
                    "quantity": 1,
                    "power_factor": "0.9",
                    "ku": "1",
                    "phase": None,
                },
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert created_feeder(payload, board_id)["reference"] == "Q1"
        assert payload["loads"][-1]["feeder_id"] == created_feeder(payload, board_id)["id"]
