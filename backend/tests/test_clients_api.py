from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.client_store import ClientStore
from backend.main import create_app
from backend.project_commands import CommandProjectStore

TOKEN = "web08-clients-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def make_api(tmp_path: Path) -> TestClient:
    clients = ClientStore(tmp_path / "clients.db")
    store = CommandProjectStore(root=tmp_path / "projects", client_store=clients)
    return TestClient(
        create_app(TOKEN, allow_test_host=True, project_store=store, client_store=clients)
    )


def client_payload(name: str = "Client WEB-08") -> dict[str, object]:
    return {
        "company_name": name,
        "address": "1 rue du Client",
        "country": "France",
        "contact_name": "Marie",
        "email": "marie@example.invalid",
        "phone": "+33 1 23 45 67 89",
    }


def project_payload(client_id: str | None = None) -> dict[str, object]:
    return {
        "name": "Projet WEB-08 client",
        "reference": "WEB08-CLIENT",
        "client": "Texte legacy",
        "client_id": client_id,
        "site": "Site",
        "address": "2 rue du Site",
        "author": "Qualification",
        "description": "Projet de test",
        "observations": "",
        "revision": "A",
        "standard": "NF C 15-100",
        "network": "TRI",
        "voltage_v": "400",
        "has_neutral": True,
        "voltage_ln_v": "230",
    }


def test_client_crud_archive_and_duplicate(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        empty = api.get("/api/clients", headers=AUTH)
        assert empty.status_code == 200
        assert empty.json() == {"clients": []}

        created = api.post("/api/clients", headers=AUTH, json=client_payload())
        assert created.status_code == 200, created.text
        client = created.json()
        assert client["company_name"] == "Client WEB-08"
        assert client["is_archived"] is False
        client_id = client["id"]

        listed = api.get("/api/clients", headers=AUTH)
        assert listed.status_code == 200
        assert len(listed.json()["clients"]) == 1

        duplicate = api.post("/api/clients", headers=AUTH, json=client_payload())
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "CLIENT_DUPLICATE"

        invalid = api.post(
            "/api/clients",
            headers=AUTH,
            json={**client_payload("Autre client"), "email": "invalide"},
        )
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "CLIENT_EMAIL_INVALIDE"

        updated = api.put(
            f"/api/clients/{client_id}",
            headers=AUTH,
            json={**client_payload("Client WEB-08 modifié"), "phone": "+33 9 99 99 99 99"},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["company_name"] == "Client WEB-08 modifié"

        archived = api.post(f"/api/clients/{client_id}/archive", headers=AUTH)
        assert archived.status_code == 200
        assert archived.json()["is_archived"] is True

        reactivated = api.post(f"/api/clients/{client_id}/reactivate", headers=AUTH)
        assert reactivated.status_code == 200
        assert reactivated.json()["is_archived"] is False

        missing = api.get("/api/clients/00000000-0000-0000-0000-000000000000", headers=AUTH)
        assert missing.status_code == 404
        assert missing.json()["code"] == "CLIENT_NOT_FOUND"


def test_project_association_and_legacy_mode(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        client = api.post(
            "/api/clients", headers=AUTH, json=client_payload("Client associé")
        ).json()

        created = api.post("/api/project/new", headers=AUTH, json=project_payload(client["id"]))
        assert created.status_code == 200, created.text
        payload = created.json()
        assert payload["project"]["client_id"] == client["id"]
        assert payload["project"]["client"] == "Client associé"
        assert payload["project"]["client_snapshot"]["client_id"] == client["id"]
        assert payload["project"]["client_snapshot"]["address"] == "1 rue du Client"
        assert payload["web"]["address"] == "2 rue du Site"

        legacy = api.post("/api/project/new", headers=AUTH, json=project_payload(None))
        assert legacy.status_code == 200, legacy.text
        legacy_payload = legacy.json()
        assert legacy_payload["project"]["client_id"] is None
        assert legacy_payload["project"]["client"] == "Texte legacy"


def test_project_client_change_and_snapshot_is_not_auto_refreshed(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        first = api.post("/api/clients", headers=AUTH, json=client_payload("Client A")).json()
        second = api.post("/api/clients", headers=AUTH, json=client_payload("Client B")).json()
        created = api.post("/api/project/new", headers=AUTH, json=project_payload(first["id"]))
        assert created.status_code == 200
        payload = created.json()

        changed = api.post(
            "/api/project/general",
            headers=AUTH,
            json={
                "expected_revision": payload["state"]["revision"],
                "name": payload["project"]["name"],
                "reference": payload["project"]["reference"],
                "client": "Client A",
                "client_id": second["id"],
                "site": payload["web"]["site"],
                "address": payload["web"]["address"],
                "author": payload["web"]["created_by"],
                "description": payload["project"]["description"],
                "observations": payload["web"]["observations"],
                "revision": "A",
                "standard": "NF C 15-100",
            },
        )
        assert changed.status_code == 200, changed.text
        changed_payload = changed.json()
        assert changed_payload["project"]["client_id"] == second["id"]
        assert changed_payload["project"]["client"] == "Client B"

        # Editing the client record must not rewrite the project snapshot.
        updated_client = api.put(
            f"/api/clients/{second['id']}",
            headers=AUTH,
            json={**client_payload("Client B modifié"), "address": "9 rue du Client"},
        )
        assert updated_client.status_code == 200
        current = api.get("/api/project", headers=AUTH).json()
        assert current["project"]["client"] == "Client B"
        assert current["project"]["client_snapshot"]["address"] == "1 rue du Client"


def test_project_file_list_exposes_client_and_detach_keeps_legacy(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        client = api.post(
            "/api/clients", headers=AUTH, json=client_payload("Client fichier")
        ).json()
        created = api.post("/api/project/new", headers=AUTH, json=project_payload(client["id"]))
        assert created.status_code == 200
        payload = created.json()
        project_path = tmp_path / "projects" / "client-project.segyrcalc-web.json"
        saved = api.post(
            "/api/project/save",
            headers=AUTH,
            json={"path": str(project_path), "overwrite": False},
        )
        assert saved.status_code == 200, saved.text
        files = api.get("/api/project/files", headers=AUTH).json()["files"]
        linked = next(item for item in files if item["path"] == str(project_path))
        assert linked["client_id"] == client["id"]
        assert linked["client_name"] == "Client fichier"

        detached = api.post(
            "/api/project/general",
            headers=AUTH,
            json={
                "expected_revision": saved.json()["state"]["revision"],
                "name": payload["project"]["name"],
                "reference": payload["project"]["reference"],
                "client": "Ancien client libre",
                "client_id": None,
                "detach_client": True,
                "site": payload["web"]["site"],
                "address": payload["web"]["address"],
                "author": payload["web"]["created_by"],
                "description": payload["project"]["description"],
                "observations": payload["web"]["observations"],
                "revision": "A",
                "standard": "NF C 15-100",
            },
        )
        assert detached.status_code == 200, detached.text
        detached_payload = detached.json()
        assert detached_payload["project"]["client_id"] is None
        assert detached_payload["project"]["client"] == "Ancien client libre"


def test_snapshot_refresh_is_explicit(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        client = api.post(
            "/api/clients", headers=AUTH, json=client_payload("Client snapshot")
        ).json()
        created = api.post("/api/project/new", headers=AUTH, json=project_payload(client["id"]))
        assert created.status_code == 200
        payload = created.json()
        api.put(
            f"/api/clients/{client['id']}",
            headers=AUTH,
            json={**client_payload("Client snapshot"), "address": "Nouvelle adresse"},
        )
        base = {
            "expected_revision": payload["state"]["revision"],
            "name": payload["project"]["name"],
            "reference": payload["project"]["reference"],
            "client": "Client snapshot",
            "client_id": client["id"],
            "site": payload["web"]["site"],
            "address": payload["web"]["address"],
            "author": payload["web"]["created_by"],
            "description": payload["project"]["description"],
            "observations": payload["web"]["observations"],
            "revision": "A",
            "standard": "NF C 15-100",
        }
        unchanged = api.post("/api/project/general", headers=AUTH, json=base)
        assert unchanged.status_code == 200, unchanged.text
        assert unchanged.json()["project"]["client_snapshot"]["address"] == "1 rue du Client"

        refreshed = api.post(
            "/api/project/general",
            headers=AUTH,
            json={
                **base,
                "expected_revision": unchanged.json()["state"]["revision"],
                "refresh_client": True,
            },
        )
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["project"]["client_snapshot"]["address"] == "Nouvelle adresse"


def test_client_persistence_uses_injected_database(tmp_path: Path) -> None:
    db = tmp_path / "clients.db"
    first = ClientStore(db)
    created = first.create(client_payload("Persistant"))
    first.close()

    second = ClientStore(db)
    try:
        found = second.get(created["id"])
        assert found["company_name"] == "Persistant"
    finally:
        second.close()
