from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.project_commands import CommandProjectStore

TOKEN = "web03-test-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def _find_engine_worktree() -> Path:
    """Resolve the external V1.5 worktree independently of repository depth."""
    candidates: list[Path] = []
    configured_fixture = os.environ.get("SEGYR_PROJECT_FIXTURE")
    if configured_fixture:
        fixture = Path(configured_fixture).expanduser().resolve()
        if fixture.is_file():
            candidates.append(fixture.parent.parent)
    configured_source = os.environ.get("SEGYR_ENGINE_SRC")
    if configured_source:
        source = Path(configured_source).expanduser().resolve()
        candidates.append(source.parent if source.name == "src" else source)
    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / "SEGYRCALC-V1.5-UI-ERGONOMIE-01" / "worktree")
    for candidate in candidates:
        if (
            (candidate / "examples" / "recette-business-acceptance-v1.3.json").is_file()
            and (
                candidate / "fixtures" / "project_enedis_c5.calcelect-v1.4.json"
            ).is_file()
        ):
            return candidate
    raise FileNotFoundError(
        "Worktree SEGYRCALC-V1.5 introuvable; définir SEGYR_ENGINE_SRC "
        "ou SEGYR_PROJECT_FIXTURE."
    )


WORKTREE = _find_engine_worktree()
EXAMPLES = WORKTREE / "examples"
V14_FIXTURE = WORKTREE / "fixtures" / "project_enedis_c5.calcelect-v1.4.json"


def client(root: Path) -> TestClient:
    store = CommandProjectStore(
        root=root,
        read_roots=(EXAMPLES, WORKTREE / "fixtures"),
    )
    return TestClient(create_app(TOKEN, allow_test_host=True, project_store=store))


def current_revision(api: TestClient) -> int:
    response = api.get("/api/project", headers=AUTH)
    assert response.status_code == 200, response.text
    return int(response.json()["state"]["revision"])


def new_payload() -> dict[str, object]:
    return {
        "name": "Projet WEB-03 test",
        "reference": "WEB03-TEST",
        "client": "Client test",
        "site": "Site test",
        "address": "1 rue de test",
        "author": "Qualification",
        "description": "Projet de qualification",
        "observations": "Aucune",
        "revision": "A",
        "standard": "NF C 15-100",
        "network": "TRI",
        "voltage_v": "400",
        "has_neutral": True,
        "voltage_ln_v": "230",
    }


def test_project_cycle_create_edit_save_close_open(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        created = api.post("/api/project/new", headers=AUTH, json=new_payload())
        assert created.status_code == 200, created.text
        payload = created.json()
        assert payload["state"]["dirty"] is True
        assert payload["state"]["file_path"] is None
        assert payload["project"]["board_count"] == 1
        assert payload["boards"][0]["type"] == "TGBT"
        assert payload["web"]["site"] == "Site test"
        assert payload["web"]["address"] == "1 rue de test"

        updated = api.post(
            "/api/project/general",
            headers=AUTH,
            json={
                "expected_revision": payload["state"]["revision"],
                "name": "Projet WEB-03 modifié",
                "reference": "WEB03-TEST",
                "client": "Client test",
                "site": "Site modifié",
                "address": "2 rue de test",
                "author": "Qualification",
                "description": "Description modifiée",
                "observations": "Observation",
                "revision": "B",
                "standard": "NF C 15-100",
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["project"]["name"] == "Projet WEB-03 modifié"

        board = api.post(
            "/api/project/boards",
            headers=AUTH,
            json={
                "expected_revision": updated.json()["state"]["revision"],
                "parent_board_id": "TGBT-01",
                "designation": "Tableau divisionnaire test",
                "description": "Créé par test",
                "has_neutral": True,
                "voltage_ln_v": "230",
            },
        )
        assert board.status_code == 200, board.text
        assert board.json()["project"]["board_count"] == 2
        new_board = next(item for item in board.json()["boards"] if item["type"] == "DIVISIONNAIRE")

        feeder = api.post(
            "/api/project/feeders",
            headers=AUTH,
            json={
                "expected_revision": board.json()["state"]["revision"],
                "parent_board_id": new_board["id"],
                "designation": "Départ test",
                "description": "",
                "ks": "0.9",
                "phase": None,
                "has_neutral": True,
                "voltage_ln_v": "230",
            },
        )
        assert feeder.status_code == 200, feeder.text
        new_feeder = max(feeder.json()["feeders"], key=lambda item: item["id"])

        load = api.post(
            "/api/project/loads",
            headers=AUTH,
            json={
                "expected_revision": feeder.json()["state"]["revision"],
                "feeder_id": new_feeder["id"],
                "designation": "Récepteur test",
                "network": "TRI",
                "voltage_v": "400",
                "nominal_power": "5000",
                "power_unit": "W",
                "quantity": 2,
                "power_factor": "0.9",
                "ku": "0.8",
                "phase": None,
            },
        )
        assert load.status_code == 200, load.text
        assert load.json()["project"]["load_count"] == 1
        assert load.json()["state"]["dirty"] is True
        assert load.json()["state"]["stale"] is False
        assert load.json()["state"]["calculation_revision"] == load.json()["state"]["revision"]

        target = tmp_path / "projet-test.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save", headers=AUTH, json={"path": str(target), "overwrite": False}
        )
        assert saved.status_code == 200, saved.text
        assert target.is_file()
        assert saved.json()["state"]["dirty"] is False
        envelope = json.loads(target.read_text(encoding="utf-8"))
        assert envelope["schema"] == "SEGYRCALC_WEB_PROJECT"
        assert "calcelect_v14" in envelope

        refused = api.post(
            "/api/project/save", headers=AUTH, json={"path": str(target), "overwrite": False}
        )
        assert refused.status_code == 409

        closed = api.post("/api/project/close", headers=AUTH)
        assert closed.status_code == 200
        assert api.get("/api/project", headers=AUTH).status_code == 404

        reopened = api.post("/api/project/open", headers=AUTH, json={"path": str(target)})
        assert reopened.status_code == 200, reopened.text
        reopened_payload = reopened.json()
        assert reopened_payload["project"]["board_count"] == 2
        assert reopened_payload["project"]["feeder_count"] == 2
        assert reopened_payload["project"]["load_count"] == 1
        assert reopened_payload["state"]["dirty"] is False
        assert reopened_payload["state"]["read_only_source"] is False
        assert reopened_payload["state"]["stale"] is False
        assert reopened_payload["totals"]["p_installed_w"] is not None


def test_historical_project_is_read_only_and_save_as_creates_new_file(tmp_path: Path) -> None:
    historical = EXAMPLES / "recette-business-acceptance-v1.3.json"
    with client(tmp_path) as api:
        opened = api.post("/api/project/open", headers=AUTH, json={"path": str(historical)})
        assert opened.status_code == 200, opened.text
        payload = opened.json()
        assert payload["state"]["read_only_source"] is True
        assert payload["state"]["source_format"] == "V1.3"
        assert payload["state"]["dirty"] is False

        refused = api.post(
            "/api/project/save", headers=AUTH, json={"path": None, "overwrite": False}
        )
        assert refused.status_code == 409
        assert refused.json()["code"] == "PROJET_HISTORIQUE_LECTURE_SEULE"

        target = tmp_path / "copie-historique.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save-as", headers=AUTH, json={"path": str(target), "overwrite": False}
        )
        assert saved.status_code == 200, saved.text
        assert target.is_file()
        assert saved.json()["state"]["read_only_source"] is False


def test_v14_project_is_read_only_and_preserves_its_model(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        opened = api.post("/api/project/open", headers=AUTH, json={"path": str(V14_FIXTURE)})
        assert opened.status_code == 200, opened.text
        payload = opened.json()
        assert payload["state"]["read_only_source"] is True
        assert payload["state"]["source_format"] == "V1.4"
        assert payload["project"]["board_count"] >= 1
        target = tmp_path / "copie-v14.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save-as", headers=AUTH, json={"path": str(target), "overwrite": False}
        )
        assert saved.status_code == 200, saved.text
        assert target.is_file()


def test_path_traversal_and_invalid_delete_are_rejected(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        api.post("/api/project/new", headers=AUTH, json=new_payload())
        outside = api.post("/api/project/open", headers=AUTH, json={"path": r"C:\Windows\win.ini"})
        assert outside.status_code == 403
        assert outside.json()["code"] == "CHEMIN_NON_AUTORISE"

        bad_delete = api.delete(
            f"/api/project/boards/TGBT-01?expected_revision={current_revision(api)}",
            headers=AUTH,
        )
        assert bad_delete.status_code == 422
        assert bad_delete.json()["code"] in {
            "TABLEAU_UTILISE",
            "TABLEAU_INTROUVABLE",
            "SUPPRESSION_RACINE_REFUSEE",
        }

        bad_load = api.post(
            "/api/project/loads",
            headers=AUTH,
            json={
                "expected_revision": current_revision(api),
                "feeder_id": "DEP-inexistant",
                "designation": "Récepteur invalide",
                "network": "MONO",
                "voltage_v": "230",
                "nominal_power": "1000",
                "power_unit": "W",
                "quantity": 1,
                "power_factor": "0.9",
                "ku": "1",
                "phase": "L1",
            },
        )
        assert bad_load.status_code == 404


def test_files_endpoint_and_save_as(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        api.post("/api/project/new", headers=AUTH, json=new_payload())
        first = tmp_path / "premier.segyrcalc-web.json"
        assert (
            api.post(
                "/api/project/save", headers=AUTH, json={"path": str(first), "overwrite": False}
            ).status_code
            == 200
        )
        second = tmp_path / "second.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save-as", headers=AUTH, json={"path": str(second), "overwrite": False}
        )
        assert saved.status_code == 200
        assert saved.json()["state"]["file_path"] == str(second)
        files = api.get("/api/project/files", headers=AUTH)
        assert files.status_code == 200
        names = {item["name"] for item in files.json()["files"]}
        assert "premier.segyrcalc-web.json" in names
        assert "second.segyrcalc-web.json" in names


def test_duplicate_creates_new_project_identity(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        api.post("/api/project/new", headers=AUTH, json=new_payload())
        first = tmp_path / "original.segyrcalc-web.json"
        assert (
            api.post(
                "/api/project/save", headers=AUTH, json={"path": str(first), "overwrite": False}
            ).status_code
            == 200
        )
        second = tmp_path / "copie.segyrcalc-web.json"
        duplicated = api.post(
            "/api/project/duplicate", headers=AUTH, json={"path": str(second), "overwrite": False}
        )
        assert duplicated.status_code == 200, duplicated.text
        assert duplicated.json()["state"]["file_path"] == str(second)
        assert "(copie)" in duplicated.json()["project"]["name"]
        original = json.loads(first.read_text(encoding="utf-8"))
        copy = json.loads(second.read_text(encoding="utf-8"))
        assert (
            original["calcelect_v14"]["project"]["electrical"]["project_id"]
            != copy["calcelect_v14"]["project"]["electrical"]["project_id"]
        )


def test_unicode_filename_and_corrupted_file(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        created = api.post("/api/project/new", headers=AUTH, json=new_payload())
        assert created.status_code == 200
        target = tmp_path / "projet-électricité- qualification.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save", headers=AUTH, json={"path": str(target), "overwrite": False}
        )
        assert saved.status_code == 200, saved.text
        assert target.is_file()
        reopened = api.post("/api/project/open", headers=AUTH, json={"path": str(target)})
        assert reopened.status_code == 200, reopened.text

        corrupted = tmp_path / "corrompu.segyrcalc-web.json"
        corrupted.write_text("{ pas un json", encoding="utf-8")
        refused = api.post("/api/project/open", headers=AUTH, json={"path": str(corrupted)})
        assert refused.status_code == 422
        assert refused.json()["code"] in {"PROJET_JSON_INVALIDE", "PROJET_LECTURE_ECHEC"}


def test_save_outside_root_and_historical_overwrite_are_refused(tmp_path: Path) -> None:
    historical = EXAMPLES / "recette-business-acceptance-v1.3.json"
    with client(tmp_path) as api:
        api.post("/api/project/new", headers=AUTH, json=new_payload())
        outside = tmp_path.parent / "hors-perimetre.segyrcalc-web.json"
        refused = api.post(
            "/api/project/save", headers=AUTH, json={"path": str(outside), "overwrite": True}
        )
        assert refused.status_code == 403
        assert refused.json()["code"] == "CHEMIN_NON_AUTORISE"

        opened = api.post("/api/project/open", headers=AUTH, json={"path": str(historical)})
        assert opened.status_code == 200
        historical_write = api.post(
            "/api/project/save-as", headers=AUTH, json={"path": str(historical), "overwrite": True}
        )
        assert historical_write.status_code == 403
        assert historical_write.json()["code"] == "CHEMIN_NON_AUTORISE"


def test_oversized_request_is_rejected(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        payload = new_payload()
        payload["observations"] = "x" * 20_000
        response = api.post("/api/project/new", headers=AUTH, json=payload)
        assert response.status_code == 413


def test_overwrite_creates_backup_of_previous_file(tmp_path: Path) -> None:
    target = tmp_path / "sauvegarde.segyrcalc-web.json"
    with client(tmp_path) as api:
        api.post("/api/project/new", headers=AUTH, json=new_payload())
        assert (
            api.post(
                "/api/project/save", headers=AUTH, json={"path": str(target), "overwrite": False}
            ).status_code
            == 200
        )
        first = target.read_bytes()
        api.post(
            "/api/project/general",
            headers=AUTH,
            json={
                "expected_revision": current_revision(api),
                "name": "Projet sauvegardé",
                "reference": "WEB03-TEST",
                "client": "Client test",
                "site": "Site test",
                "address": "1 rue de test",
                "author": "Qualification",
                "description": "Deuxième version",
                "observations": "",
                "revision": "B",
                "standard": "NF C 15-100",
            },
        )
        assert (
            api.post(
                "/api/project/save", headers=AUTH, json={"path": str(target), "overwrite": True}
            ).status_code
            == 200
        )
        backup = target.with_name(target.name + ".bak")
        assert backup.is_file()
        assert backup.read_bytes() == first


def test_read_only_target_is_reported_without_losing_previous_file(tmp_path: Path) -> None:
    target = tmp_path / "verrouille.segyrcalc-web.json"
    with client(tmp_path) as api:
        api.post("/api/project/new", headers=AUTH, json=new_payload())
        assert (
            api.post(
                "/api/project/save", headers=AUTH, json={"path": str(target), "overwrite": False}
            ).status_code
            == 200
        )
        before = target.read_bytes()
        try:
            target.chmod(stat.S_IREAD)
            refused = api.post(
                "/api/project/save", headers=AUTH, json={"path": str(target), "overwrite": True}
            )
            assert refused.status_code == 422
            assert target.is_file()
            assert target.read_bytes() == before
        finally:
            target.chmod(stat.S_IWRITE | stat.S_IREAD)


def test_long_windows_path_remains_writable(tmp_path: Path) -> None:
    target = tmp_path / (("a" * 180) + ".segyrcalc-web.json")
    with client(tmp_path) as api:
        api.post("/api/project/new", headers=AUTH, json=new_payload())
        saved = api.post(
            "/api/project/save", headers=AUTH, json={"path": str(target), "overwrite": False}
        )
        assert saved.status_code == 200, saved.text
        assert target.is_file()
        opened = api.post("/api/project/open", headers=AUTH, json={"path": str(target)})
        assert opened.status_code == 200, opened.text


def _scaffold(api: TestClient) -> dict[str, Any]:
    created = api.post("/api/project/new", headers=AUTH, json=new_payload())
    assert created.status_code == 200, created.text
    board = api.post(
        "/api/project/boards",
        headers=AUTH,
        json={
            "expected_revision": created.json()["state"]["revision"],
            "parent_board_id": "TGBT-01",
            "designation": "Tableau WEB-04",
            "has_neutral": True,
            "voltage_ln_v": "230",
        },
    )
    assert board.status_code == 200, board.text
    new_board = next(item for item in board.json()["boards"] if item["type"] == "DIVISIONNAIRE")
    feeder = api.post(
        "/api/project/feeders",
        headers=AUTH,
        json={
            "expected_revision": board.json()["state"]["revision"],
            "parent_board_id": new_board["id"],
            "designation": "Départ WEB-04",
            "ks": "0.9",
            "has_neutral": True,
        },
    )
    assert feeder.status_code == 200, feeder.text
    new_feeder = next(item for item in feeder.json()["feeders"] if item["id"] != "DEP-01")
    return {
        "created": created.json(),
        "board": board.json(),
        "feeder": feeder.json(),
        "new_board": new_board,
        "new_feeder": new_feeder,
    }


def _add_load(api: TestClient, feeder_id: str, designation: str) -> dict[str, Any]:
    response = api.post(
        "/api/project/loads",
        headers=AUTH,
        json={
            "expected_revision": current_revision(api),
            "feeder_id": feeder_id,
            "designation": designation,
            "network": "TRI",
            "voltage_v": "400",
            "nominal_power": "5000",
            "power_unit": "W",
            "quantity": 2,
            "power_factor": "0.9",
            "ku": "0.8",
            "phase": None,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_revision_obsolete_is_rejected_without_mutation(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        created = api.post("/api/project/new", headers=AUTH, json=new_payload())
        stale = created.json()["state"]["revision"]
        updated = api.post(
            "/api/project/general",
            headers=AUTH,
            json={
                "expected_revision": stale,
                "name": "Projet révisé",
                "reference": "WEB04-TEST",
                "client": "Client test",
                "site": "Site test",
                "address": "1 rue de test",
                "author": "Qualification",
                "description": "",
                "observations": "",
                "revision": "B",
                "standard": "NF C 15-100",
            },
        )
        assert updated.status_code == 200
        refused = api.post(
            "/api/project/boards",
            headers=AUTH,
            json={
                "expected_revision": stale,
                "parent_board_id": "TGBT-01",
                "designation": "Tableau obsolète",
                "has_neutral": True,
                "voltage_ln_v": "230",
            },
        )
        assert refused.status_code == 409
        assert refused.json()["code"] == "REVISION_OBSOLETE"
        current = api.get("/api/project", headers=AUTH).json()
        assert current["project"]["board_count"] == 1
        assert current["state"]["revision"] == updated.json()["state"]["revision"]


def test_undo_redo_restores_architecture_and_results(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        load = _add_load(api, scaffold["new_feeder"]["id"], "Récepteur WEB-04")
        after_load = load["state"]["revision"]
        assert load["project"]["load_count"] == 1

        undone = api.post("/api/project/undo", headers=AUTH, json={"expected_revision": after_load})
        assert undone.status_code == 200, undone.text
        assert undone.json()["project"]["load_count"] == 0
        assert undone.json()["state"]["can_redo"] is True
        assert "Création" in undone.json()["state"]["undo_label"]

        undone2 = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": undone.json()["state"]["revision"]},
        )
        assert undone2.status_code == 200, undone2.text
        assert undone2.json()["project"]["feeder_count"] == 1
        assert undone2.json()["project"]["board_count"] == 2

        redone = api.post(
            "/api/project/redo",
            headers=AUTH,
            json={"expected_revision": undone2.json()["state"]["revision"]},
        )
        assert redone.status_code == 200, redone.text
        assert redone.json()["project"]["feeder_count"] == 2
        redone2 = api.post(
            "/api/project/redo",
            headers=AUTH,
            json={"expected_revision": redone.json()["state"]["revision"]},
        )
        assert redone2.status_code == 200, redone2.text
        assert redone2.json()["project"]["load_count"] == 1
        assert redone2.json()["state"]["dirty"] is True


def test_undo_to_saved_state_is_clean_and_redo_is_dirty(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        target = tmp_path / "undo-save.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save", headers=AUTH, json={"path": str(target), "overwrite": False}
        )
        assert saved.status_code == 200
        _add_load(api, scaffold["new_feeder"]["id"], "Récepteur sauvegarde")
        dirty_payload = api.get("/api/project", headers=AUTH).json()
        assert dirty_payload["state"]["dirty"] is True
        undone = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": dirty_payload["state"]["revision"]},
        )
        assert undone.status_code == 200, undone.text
        assert undone.json()["state"]["dirty"] is False
        redone = api.post(
            "/api/project/redo",
            headers=AUTH,
            json={"expected_revision": undone.json()["state"]["revision"]},
        )
        assert redone.status_code == 200, redone.text
        assert redone.json()["state"]["dirty"] is True


def test_move_load_between_feeders_preserves_results(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        second = api.post(
            "/api/project/feeders",
            headers=AUTH,
            json={
                "expected_revision": current_revision(api),
                "parent_board_id": scaffold["new_board"]["id"],
                "designation": "Départ destination",
                "ks": "0.9",
                "has_neutral": True,
            },
        )
        assert second.status_code == 200, second.text
        destination = max(second.json()["feeders"], key=lambda item: item["id"])
        load = _add_load(api, scaffold["new_feeder"]["id"], "Récepteur à déplacer")
        before_total = load["totals"]["p_installed_w"]
        moved = api.post(
            f"/api/project/loads/{load['loads'][0]['id']}/move",
            headers=AUTH,
            json={
                "expected_revision": load["state"]["revision"],
                "destination_feeder_id": destination["id"],
            },
        )
        assert moved.status_code == 200, moved.text
        payload = moved.json()
        assert payload["loads"][0]["feeder_id"] == destination["id"]
        assert payload["totals"]["p_installed_w"] == before_total
        assert "Déplacement" in payload["state"]["undo_label"]


def test_move_feeder_preserves_its_loads(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        load = _add_load(api, scaffold["new_feeder"]["id"], "Récepteur départ mobile")
        moved = api.post(
            f"/api/project/feeders/{scaffold['new_feeder']['id']}/move",
            headers=AUTH,
            json={
                "expected_revision": load["state"]["revision"],
                "destination_board_id": "TGBT-01",
            },
        )
        assert moved.status_code == 200, moved.text
        payload = moved.json()
        feeder = next(f for f in payload["feeders"] if f["id"] == scaffold["new_feeder"]["id"])
        assert feeder["parent_board_id"] == "TGBT-01"
        assert feeder["member_count"] == 1
        assert payload["project"]["load_count"] == 1


def test_move_board_rejects_cycle_and_accepts_valid_destination(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        child = api.post(
            "/api/project/boards",
            headers=AUTH,
            json={
                "expected_revision": current_revision(api),
                "parent_board_id": scaffold["new_board"]["id"],
                "designation": "Tableau enfant",
                "has_neutral": True,
                "voltage_ln_v": "230",
            },
        )
        assert child.status_code == 200, child.text
        child_board = next(
            item for item in child.json()["boards"] if item["designation"] == "Tableau enfant"
        )
        cycle = api.post(
            f"/api/project/boards/{scaffold['new_board']['id']}/move",
            headers=AUTH,
            json={
                "expected_revision": child.json()["state"]["revision"],
                "destination_board_id": child_board["id"],
            },
        )
        assert cycle.status_code == 422
        assert cycle.json()["code"] == "CYCLE_INTERDIT"
        valid = api.post(
            f"/api/project/boards/{child_board['id']}/move",
            headers=AUTH,
            json={
                "expected_revision": child.json()["state"]["revision"],
                "destination_board_id": "TGBT-01",
            },
        )
        assert valid.status_code == 200, valid.text
        moved_board = next(
            item for item in valid.json()["boards"] if item["id"] == child_board["id"]
        )
        moved_feeder = next(
            item
            for item in valid.json()["feeders"]
            if item["id"] == moved_board["parent_feeder_id"]
        )
        assert moved_feeder["parent_board_id"] == "TGBT-01"


def test_duplicate_board_subtree_and_feeder(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        load = _add_load(api, scaffold["new_feeder"]["id"], "Récepteur dupliqué")
        duplicated = api.post(
            f"/api/project/boards/{scaffold['new_board']['id']}/duplicate",
            headers=AUTH,
            json={
                "expected_revision": load["state"]["revision"],
                "destination_board_id": "TGBT-01",
            },
        )
        assert duplicated.status_code == 200, duplicated.text
        payload = duplicated.json()
        assert payload["project"]["board_count"] == 3
        assert payload["project"]["feeder_count"] == 4
        assert payload["project"]["load_count"] == 2
        original_ids = {scaffold["new_board"]["id"], scaffold["new_feeder"]["id"]}
        new_board_ids = {item["id"] for item in payload["boards"]} - {"TGBT-01"} - original_ids
        assert len(new_board_ids) == 1
        feeder_copy = api.post(
            f"/api/project/feeders/{scaffold['new_feeder']['id']}/duplicate",
            headers=AUTH,
            json={
                "expected_revision": payload["state"]["revision"],
                "destination_board_id": "TGBT-01",
            },
        )
        assert feeder_copy.status_code == 200, feeder_copy.text
        assert feeder_copy.json()["project"]["load_count"] == 3
        assert "Duplication" in feeder_copy.json()["state"]["undo_label"]


def test_duplicate_nested_board_subtree(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        _add_load(api, scaffold["new_feeder"]["id"], "Récepteur parent dupliqué")
        child = api.post(
            "/api/project/boards",
            headers=AUTH,
            json={
                "expected_revision": current_revision(api),
                "parent_board_id": scaffold["new_board"]["id"],
                "designation": "Tableau enfant duplication",
                "has_neutral": True,
                "voltage_ln_v": "230",
            },
        )
        assert child.status_code == 200, child.text
        child_board = next(
            item
            for item in child.json()["boards"]
            if item["designation"] == "Tableau enfant duplication"
        )
        child_feeder = api.post(
            "/api/project/feeders",
            headers=AUTH,
            json={
                "expected_revision": child.json()["state"]["revision"],
                "parent_board_id": child_board["id"],
                "designation": "Départ enfant duplication",
                "ks": "0.9",
                "has_neutral": True,
            },
        )
        assert child_feeder.status_code == 200, child_feeder.text
        terminal = next(
            item
            for item in child_feeder.json()["feeders"]
            if item["designation"] == "Départ enfant duplication"
        )
        load = _add_load(api, terminal["id"], "Récepteur enfant dupliqué")
        duplicated = api.post(
            f"/api/project/boards/{scaffold['new_board']['id']}/duplicate",
            headers=AUTH,
            json={
                "expected_revision": load["state"]["revision"],
                "destination_board_id": "TGBT-01",
            },
        )
        assert duplicated.status_code == 200, duplicated.text
        payload = duplicated.json()
        assert payload["project"]["board_count"] == 5
        assert payload["project"]["feeder_count"] == 8
        assert payload["project"]["load_count"] == 4


def test_delete_preview_and_controlled_cascade(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        load = _add_load(api, scaffold["new_feeder"]["id"], "Récepteur supprimable")
        preview = api.get(
            f"/api/project/deletion-preview/board/{scaffold['new_board']['id']}",
            headers=AUTH,
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["boards"] == 1
        assert preview.json()["feeders"] == 2
        assert preview.json()["loads"] == 1
        deleted = api.delete(
            f"/api/project/boards/{scaffold['new_board']['id']}?expected_revision={load['state']['revision']}&cascade=true",
            headers=AUTH,
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["project"]["board_count"] == 1
        assert deleted.json()["project"]["load_count"] == 0
        undone = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": deleted.json()["state"]["revision"]},
        )
        assert undone.status_code == 200, undone.text
        assert undone.json()["project"]["board_count"] == 2
        assert undone.json()["project"]["load_count"] == 1


def test_nested_board_cascade_deletes_descendants_and_undo_restores(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        _add_load(api, scaffold["new_feeder"]["id"], "Récepteur niveau 1")
        child = api.post(
            "/api/project/boards",
            headers=AUTH,
            json={
                "expected_revision": current_revision(api),
                "parent_board_id": scaffold["new_board"]["id"],
                "designation": "Tableau enfant cascade",
                "has_neutral": True,
                "voltage_ln_v": "230",
            },
        )
        assert child.status_code == 200, child.text
        child_board = next(
            item
            for item in child.json()["boards"]
            if item["designation"] == "Tableau enfant cascade"
        )
        child_feeder = api.post(
            "/api/project/feeders",
            headers=AUTH,
            json={
                "expected_revision": child.json()["state"]["revision"],
                "parent_board_id": child_board["id"],
                "designation": "Départ enfant cascade",
                "ks": "0.9",
                "has_neutral": True,
            },
        )
        assert child_feeder.status_code == 200, child_feeder.text
        terminal = next(
            item
            for item in child_feeder.json()["feeders"]
            if item["designation"] == "Départ enfant cascade"
        )
        load = _add_load(api, terminal["id"], "Récepteur niveau 2")
        preview = api.get(
            f"/api/project/deletion-preview/board/{scaffold['new_board']['id']}",
            headers=AUTH,
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["boards"] == 2
        assert preview.json()["loads"] == 2
        deleted = api.delete(
            f"/api/project/boards/{scaffold['new_board']['id']}?expected_revision={load['state']['revision']}&cascade=true",
            headers=AUTH,
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["project"]["board_count"] == 1
        assert deleted.json()["project"]["feeder_count"] == 0
        assert deleted.json()["project"]["load_count"] == 0
        undone = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": deleted.json()["state"]["revision"]},
        )
        assert undone.status_code == 200, undone.text
        assert undone.json()["project"]["board_count"] == 3
        assert undone.json()["project"]["load_count"] == 2


def test_power_balance_payload_exposes_phases_coherence_and_unavailable_fields(
    tmp_path: Path,
) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        load = _add_load(api, scaffold["new_feeder"]["id"], "Récepteur bilan")
        payload = api.get("/api/project", headers=AUTH).json()
        assert payload["totals"]["q_phases"]["l1"] is not None
        assert payload["totals"]["s_phases"]["l1"] is not None
        assert payload["boards"][0]["q_phases"]["l1"] is not None
        assert payload["boards"][0]["p_phases"]["l1"] is not None
        assert payload["feeders"][0]["q_phases"]["l1"] is not None
        assert payload["feeders"][0]["s_phases"]["l1"] is not None
        assert payload["coherence"]["status"] == "PASS"
        assert payload["coherence"]["orphan_load_ids"] == []
        assert any(item["id"] == "engine_result" for item in payload["coherence"]["checks"])
        receiver = payload["loads"][0]
        assert receiver["current_available"] is True
        assert receiver["apparent_power_available"] is True
        assert receiver["s_after_ks_va"] is not None
        assert receiver["current_a"] is not None
        assert receiver["current_real_a"] is not None
        assert load["project"]["load_count"] == 1


def test_ku_and_ks_changes_recalculate_and_undo(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        load = _add_load(api, scaffold["new_feeder"]["id"], "Récepteur coefficient")
        receiver = load["loads"][0]
        before_ku = receiver["p_after_ku_w"]
        updated = api.put(
            f"/api/project/loads/{receiver['id']}",
            headers=AUTH,
            json={
                "expected_revision": load["state"]["revision"],
                "feeder_id": receiver["feeder_id"],
                "designation": receiver["designation"],
                "network": receiver["network"],
                "voltage_v": receiver["voltage_v"],
                "nominal_power": receiver["nominal_power"],
                "power_unit": receiver["power_unit"],
                "quantity": receiver["quantity"],
                "power_factor": receiver["power_factor"],
                "ku": "0.5",
                "phase": receiver["phase"],
            },
        )
        assert updated.status_code == 200, updated.text
        after_ku = updated.json()["loads"][0]["p_after_ku_w"]
        assert after_ku != before_ku
        undone = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": updated.json()["state"]["revision"]},
        )
        assert undone.status_code == 200
        assert undone.json()["loads"][0]["p_after_ku_w"] == before_ku

        feeder_payload = next(
            item for item in undone.json()["feeders"] if item["id"] == scaffold["new_feeder"]["id"]
        )
        before_ks = feeder_payload["p_after_ks_w"]
        feeder_update = api.put(
            f"/api/project/feeders/{feeder_payload['id']}",
            headers=AUTH,
            json={
                "expected_revision": undone.json()["state"]["revision"],
                "designation": feeder_payload["designation"],
                "description": feeder_payload["description"],
                "ks": "0.5",
                "phase": feeder_payload["phase"],
                "has_neutral": feeder_payload["has_neutral"],
                "voltage_ln_v": feeder_payload["voltage_ln_v"],
            },
        )
        assert feeder_update.status_code == 200, feeder_update.text
        updated_feeder = next(
            item for item in feeder_update.json()["feeders"] if item["id"] == feeder_payload["id"]
        )
        assert updated_feeder["p_after_ks_w"] != before_ks


def test_precision_is_preserved_after_save_and_reopen(tmp_path: Path) -> None:
    target = tmp_path / "precision.segyrcalc-web.json"
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        load = _add_load(api, scaffold["new_feeder"]["id"], "Récepteur précision")
        before = load["totals"]
        assert any(len(str(value)) > 20 for value in before.values() if isinstance(value, str))
        saved = api.post(
            "/api/project/save",
            headers=AUTH,
            json={"path": str(target), "overwrite": False},
        )
        assert saved.status_code == 200
        api.post("/api/project/close", headers=AUTH)
        reopened = api.post("/api/project/open", headers=AUTH, json={"path": str(target)})
        assert reopened.status_code == 200
        after = reopened.json()["totals"]
        for key in (
            "p_installed_w",
            "p_after_ku_w",
            "p_after_ks_w",
            "q_after_ks_var",
            "s_after_ks_va",
            "neutral_current_a",
            "unbalance_percent",
        ):
            assert after[key] == before[key]


def test_failed_command_is_not_added_to_history(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        api.post("/api/project/new", headers=AUTH, json=new_payload())
        before = api.get("/api/project", headers=AUTH).json()["state"]["history_length"]
        failed = api.post(
            "/api/project/loads",
            headers=AUTH,
            json={
                "expected_revision": current_revision(api),
                "feeder_id": "DEP-inexistant",
                "designation": "Récepteur invalide",
                "network": "MONO",
                "voltage_v": "230",
                "nominal_power": "1000",
                "power_unit": "W",
                "quantity": 1,
                "power_factor": "0.9",
                "ku": "1",
                "phase": "L1",
            },
        )
        assert failed.status_code == 404
        after = api.get("/api/project", headers=AUTH).json()["state"]["history_length"]
        assert after == before


def test_history_limit_is_bounded(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        api.post("/api/project/new", headers=AUTH, json=new_payload())
        for index in range(55):
            response = api.post(
                "/api/project/general",
                headers=AUTH,
                json={
                    "expected_revision": current_revision(api),
                    "name": f"Projet historique {index}",
                    "reference": "WEB04-TEST",
                    "client": "Client test",
                    "site": "Site test",
                    "address": "1 rue de test",
                    "author": "Qualification",
                    "description": "",
                    "observations": "",
                    "revision": "A",
                    "standard": "NF C 15-100",
                },
            )
            assert response.status_code == 200, response.text
        state = api.get("/api/project", headers=AUTH).json()["state"]
        assert state["undo_depth"] == state["history_limit"]
        assert state["history_length"] <= state["history_limit"]


def test_save_after_undo_and_redo_reopens_without_divergence(tmp_path: Path) -> None:
    target = tmp_path / "undo-redo-persistance.segyrcalc-web.json"
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        load = _add_load(api, scaffold["new_feeder"]["id"], "Récepteur persistant")
        undone = api.post(
            "/api/project/undo",
            headers=AUTH,
            json={"expected_revision": load["state"]["revision"]},
        )
        assert undone.status_code == 200
        redone = api.post(
            "/api/project/redo",
            headers=AUTH,
            json={"expected_revision": undone.json()["state"]["revision"]},
        )
        assert redone.status_code == 200
        saved = api.post(
            "/api/project/save",
            headers=AUTH,
            json={"path": str(target), "overwrite": False},
        )
        assert saved.status_code == 200, saved.text
        before_close = api.get("/api/project", headers=AUTH).json()
        api.post("/api/project/close", headers=AUTH)
        reopened = api.post("/api/project/open", headers=AUTH, json={"path": str(target)})
        assert reopened.status_code == 200, reopened.text
        after_open = reopened.json()
        assert after_open["project"]["load_count"] == before_close["project"]["load_count"]
        assert after_open["totals"]["p_installed_w"] == before_close["totals"]["p_installed_w"]
        assert after_open["state"]["history_length"] == 0


def test_r01_board_load_count_is_physical_and_recursive(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        scaffold = _scaffold(api)
        child_board_id = scaffold["new_board"]["id"]
        load = api.post(
            "/api/project/loads",
            headers=AUTH,
            json={
                "expected_revision": current_revision(api),
                "feeder_id": scaffold["new_feeder"]["id"],
                "designation": "Récepteur TRI R01",
                "network": "TRI",
                "voltage_v": "400",
                "nominal_power": "5000",
                "power_unit": "W",
                "quantity": 1,
                "power_factor": "0.9",
                "ku": "0.8",
                "phase": None,
            },
        )
        assert load.status_code == 200, load.text
        payload = load.json()
        boards = {item["id"]: item for item in payload["boards"]}
        assert payload["project"]["load_count"] == 1
        assert len(payload["loads"]) == 1
        assert boards["TGBT-01"]["load_count"] == 1
        assert boards[child_board_id]["load_count"] == 1
        assert payload["loads"][0]["p_after_ku_w"] is not None
