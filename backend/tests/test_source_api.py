from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.project_commands import CommandProjectStore

TOKEN = "s2-source-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def make_api(tmp_path: Path) -> TestClient:
    store = CommandProjectStore(root=tmp_path / "projects")
    return TestClient(create_app(TOKEN, allow_test_host=True, project_store=store))


def create_project(api: TestClient) -> dict:
    response = api.post(
        "/api/project/new",
        headers=AUTH,
        json={
            "name": "Projet sources S2",
            "reference": "S2-TEST",
            "client": "Client test",
            "site": "Site test",
            "address": "1 rue du Test",
            "author": "Qualification",
            "description": "Projet de qualification S2",
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


def base_source(source_type: str) -> dict:
    return {
        "id": str(uuid4()),
        "source_type": source_type,
        "reference": "SRC-01",
        "designation": "Source de test",
        "quantity": 1,
        "phase_system": None,
        "rated_power": None,
        "rated_power_unit": "KVA",
        "nominal_voltage": None,
        "voltage_unit": "V",
        "frequency_hz": None,
        "power_factor": None,
        "primary_voltage": None,
        "primary_voltage_unit": "V",
        "secondary_voltage": None,
        "secondary_voltage_unit": "V",
        "short_circuit_voltage_percent": None,
        "coupling": "",
        "operating_mode": "SINGLE",
        "active_power": None,
        "active_power_unit": "W",
        "capacity_ah": None,
        "max_current_a": None,
        "max_power_w": None,
        "technology": "",
        "connection_type": "",
        "subscribed_power_kva": None,
        "connection_power_kva": None,
    }


def source_cases() -> list[dict]:
    ac3 = base_source("AC_THREE_PHASE")
    ac3.update(
        phase_system="TRI",
        rated_power="250",
        rated_power_unit="KVA",
        nominal_voltage="400",
        frequency_hz="50",
        power_factor="0.8",
    )
    ac1 = base_source("AC_SINGLE_PHASE")
    ac1.update(
        phase_system="MONO",
        rated_power="50",
        rated_power_unit="KVA",
        nominal_voltage="230",
        frequency_hz="50",
        power_factor="0.9",
    )
    dc = base_source("DC")
    dc.update(phase_system="DC", active_power="5000", active_power_unit="W", nominal_voltage="48")
    transformer = base_source("TRANSFORMER")
    transformer.update(
        phase_system="TRI",
        rated_power="630",
        rated_power_unit="KVA",
        primary_voltage="20000",
        primary_voltage_unit="V",
        secondary_voltage="400",
        secondary_voltage_unit="V",
        frequency_hz="50",
        short_circuit_voltage_percent="5",
        coupling="Dyn11",
    )
    generator = base_source("GENERATOR")
    generator.update(
        phase_system="TRI",
        rated_power="100",
        rated_power_unit="KVA",
        nominal_voltage="400",
        frequency_hz="50",
        power_factor="0.8",
        operating_mode="BACKUP",
    )
    battery = base_source("BATTERY")
    battery.update(
        phase_system="DC",
        nominal_voltage="48",
        capacity_ah="100",
        max_current_a="100",
        max_power_w="4800",
        technology="Lithium",
    )
    enedis = base_source("ENEDIS")
    enedis.update(
        phase_system="TRI",
        nominal_voltage="400",
        connection_type="BT",
        subscribed_power_kva="36",
        connection_power_kva="36",
    )
    return [ac3, ac1, dc, transformer, generator, battery, enedis]


def test_all_seven_source_types_roundtrip_and_delete(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        for source in source_cases():
            response = api.put(
                "/api/project/source",
                headers=AUTH,
                json={"expected_revision": project["state"]["revision"], "source": source},
            )
            assert response.status_code == 200, (source["source_type"], response.text)
            project = response.json()
            assert project["source"]["source_type"] == source["source_type"]
            assert project["source"]["id"] == source["id"]
            assert project["format_version"] == "0.3.1"
            assert api.get("/api/project/source", headers=AUTH).json()["source"]["id"] == source["id"]
        deleted = api.delete(
            f"/api/project/source?expected_revision={project['state']['revision']}",
            headers=AUTH,
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["source"] is None
        assert deleted.json()["format_version"] == "0.3.0"


def test_new_project_has_no_source_and_030_is_preserved(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        assert project["source"] is None
        assert project["format_version"] == "0.3.0"
        target = tmp_path / "projects" / "sans-source.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save",
            headers=AUTH,
            json={"path": str(target), "overwrite": True},
        )
        assert saved.status_code == 200, saved.text
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "0.3.0"
        assert payload["web"]["format_version"] == "0.3.0"
        assert payload["calcelect_v14"]["project"]["source"] is None


def test_source_saved_at_031_and_preserved_on_reopen(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        source = source_cases()[0]
        updated = api.put(
            "/api/project/source",
            headers=AUTH,
            json={"expected_revision": project["state"]["revision"], "source": source},
        )
        assert updated.status_code == 200, updated.text
        project = updated.json()
        target = tmp_path / "projects" / "avec-source.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save",
            headers=AUTH,
            json={"path": str(target), "overwrite": True},
        )
        assert saved.status_code == 200, saved.text
        raw = target.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        assert payload["schema_version"] == "0.3.1"
        assert payload["web"]["format_version"] == "0.3.1"
        assert payload["calcelect_v14"]["project"]["source"]["id"] == source["id"]
        assert target.with_name(target.name + ".bak").exists() is False

        reopened = api.post(
            "/api/project/open",
            headers=AUTH,
            json={"path": str(target)},
        )
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["source"]["id"] == source["id"]


def test_source_update_is_undoable_and_redoable(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        source = source_cases()[2]
        updated = api.put(
            "/api/project/source",
            headers=AUTH,
            json={"expected_revision": project["state"]["revision"], "source": source},
        )
        assert updated.status_code == 200, updated.text
        project = updated.json()
        undone = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": project["state"]["revision"]},
        )
        assert undone.status_code == 200, undone.text
        assert undone.json()["source"] is None
        project = undone.json()
        redone = api.post(
            "/api/project/redo",
            headers=AUTH,
            json={"expected_revision": project["state"]["revision"]},
        )
        assert redone.status_code == 200, redone.text
        assert redone.json()["source"]["id"] == source["id"]


def test_source_validation_refuses_partial_or_unknown(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        project = create_project(api)
        invalid = source_cases()[0]
        invalid["source_type"] = "ONDULEUR"
        response = api.put(
            "/api/project/source",
            headers=AUTH,
            json={"expected_revision": project["state"]["revision"], "source": invalid},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "SOURCE_INVALIDE"
