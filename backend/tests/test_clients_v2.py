from __future__ import annotations

import hashlib
import sqlite3
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.client_store import ClientStore
from backend.main import create_app
from backend.project_commands import CommandProjectStore

TOKEN = "web08-l51-token"
AUTH = {"X-SEGYR-Token": TOKEN}

V1_SCHEMA = """
CREATE TABLE clients (
    id TEXT PRIMARY KEY NOT NULL,
    company_name TEXT NOT NULL CHECK (length(trim(company_name)) > 0),
    normalized_company_name TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    logo TEXT,
    is_archived INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_clients_normalized_name ON clients(normalized_company_name);
CREATE INDEX idx_clients_archived ON clients(is_archived);
CREATE INDEX idx_clients_company_name ON clients(company_name COLLATE NOCASE);
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY NOT NULL,
    applied_at TEXT NOT NULL
);
"""


def make_api(tmp_path: Path) -> TestClient:
    clients = ClientStore(tmp_path / "clients.db")
    store = CommandProjectStore(root=tmp_path / "projects", client_store=clients)
    return TestClient(
        create_app(TOKEN, allow_test_host=True, project_store=store, client_store=clients)
    )


def make_v1(db: Path) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db)
    try:
        connection.executescript(V1_SCHEMA)
        connection.execute(
            """
            INSERT INTO clients (
                id, company_name, normalized_company_name, address, country,
                contact_name, email, phone, logo, is_archived, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                "39438879-7362-419d-8406-2467afcf3ebd",
                "Client historique",
                "client historique",
                "Ancienne adresse libre",
                "France",
                "Marie Historique",
                "ancien@example.invalid",
                "+33 1 00 00 00 00",
                None,
                "2026-11-10T00:00:00+00:00",
                "2026-11-10T00:00:00+00:00",
            ),
        )
        connection.execute(
            "INSERT INTO schema_version(version, applied_at) VALUES (1, ?)",
            ("2026-11-10T00:00:00+00:00",),
        )
        connection.commit()
    finally:
        connection.close()


def test_v1_database_migrates_with_backup_and_keeps_legacy_fields(tmp_path: Path) -> None:
    db = tmp_path / "clients.db"
    make_v1(db)
    store = ClientStore(db)
    record = store.get("39438879-7362-419d-8406-2467afcf3ebd")
    assert record["company_name"] == "Client historique"
    assert record["address"] == "Ancienne adresse libre"
    assert record["address_line1"] == ""
    assert record["contact_name"] == "Marie Historique"
    assert record["country"] == "France"

    connection = sqlite3.connect(db)
    try:
        version = connection.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()[0]
        assert version == 2
        assert connection.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM company_profile").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 1
        columns = {row[1] for row in connection.execute("PRAGMA table_info(clients)")}
        assert {"address_line1", "address_line2", "postal_code", "city"} <= columns
    finally:
        connection.close()

    backups = list((tmp_path / "backups").glob("clients-v1-*.db"))
    assert len(backups) == 1
    backup_hash = hashlib.sha256(backups[0].read_bytes()).hexdigest().upper()
    assert Path(str(backups[0]) + ".sha256").read_text(encoding="utf-8").startswith(backup_hash)
    assert Path(str(backups[0]) + ".json").is_file()
    backup = sqlite3.connect(backups[0])
    try:
        assert backup.execute("SELECT version FROM schema_version").fetchone()[0] == 1
        assert backup.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 1
    finally:
        backup.close()


def test_structured_address_is_additive_and_snapshot_is_formatted(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        created = api.post(
            "/api/clients",
            headers=AUTH,
            json={
                "company_name": "Client structuré",
                "address": "Ancienne adresse",
                "address_line1": "12 rue Neuve",
                "address_line2": "Bâtiment B",
                "postal_code": "75000",
                "city": "Paris",
                "country": "France",
                "contact_name": "Contact général",
                "email": "contact@example.invalid",
                "phone": "+33 1 11 11 11 11",
            },
        )
        assert created.status_code == 200, created.text
        payload = created.json()
        assert payload["address"] == "Ancienne adresse"
        assert payload["address_line1"] == "12 rue Neuve"
        assert payload["postal_code"] == "75000"
        assert payload["city"] == "Paris"
        assert "12 rue Neuve" in payload["formatted_address"]

        # Updating another field must not rewrite the historical address.
        updated = api.put(
            f"/api/clients/{payload['id']}",
            headers=AUTH,
            json={
                "company_name": payload["company_name"],
                "address": payload["address"],
                "address_line1": payload["address_line1"],
                "address_line2": payload["address_line2"],
                "postal_code": payload["postal_code"],
                "city": payload["city"],
                "country": payload["country"],
                "contact_name": payload["contact_name"],
                "email": payload["email"],
                "phone": "+33 9 99 99 99 99",
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["address"] == "Ancienne adresse"
        assert updated.json()["phone"] == "+33 9 99 99 99 99"

        store = ClientStore(tmp_path / "clients.db")
        snapshot = store.snapshot(payload["id"])
        assert snapshot.address.startswith("12 rue Neuve")
        assert snapshot.address != "Ancienne adresse"


def test_logo_upload_read_replace_and_remove(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        created = api.post(
            "/api/clients",
            headers=AUTH,
            json={
                "company_name": "Client logo",
                "address_line1": "1 rue du Logo",
                "postal_code": "75000",
                "city": "Paris",
                "country": "France",
            },
        )
        assert created.status_code == 200, created.text
        client_id = created.json()["id"]

        image = BytesIO()
        Image.new("RGB", (8, 8), "white").save(image, format="PNG")
        png = image.getvalue()
        uploaded = api.post(
            f"/api/clients/{client_id}/logo",
            headers={**AUTH, "Content-Type": "image/png"},
            content=png,
        )
        assert uploaded.status_code == 200, uploaded.text
        assert uploaded.json()["has_logo"] is True
        assert uploaded.json()["logo"]

        fetched = api.get(f"/api/clients/{client_id}/logo", headers=AUTH)
        assert fetched.status_code == 200
        assert fetched.content == png
        assert fetched.headers["content-type"].startswith("image/png")

        replacement = BytesIO()
        Image.new("RGB", (8, 8), "black").save(replacement, format="PNG")
        replaced = api.post(
            f"/api/clients/{client_id}/logo",
            headers={**AUTH, "Content-Type": "image/png"},
            content=replacement.getvalue(),
        )
        assert replaced.status_code == 200, replaced.text
        fetched_replacement = api.get(f"/api/clients/{client_id}/logo", headers=AUTH)
        assert fetched_replacement.content == replacement.getvalue()
        assert len(list((tmp_path / "logos").glob("*"))) == 1

        invalid = api.post(
            f"/api/clients/{client_id}/logo",
            headers={**AUTH, "Content-Type": "image/png"},
            content=b"not-an-image",
        )
        assert invalid.status_code == 422

        removed = api.delete(f"/api/clients/{client_id}/logo", headers=AUTH)
        assert removed.status_code == 200, removed.text
        assert removed.json()["has_logo"] is False
        missing = api.get(f"/api/clients/{client_id}/logo", headers=AUTH)
        assert missing.status_code == 404
