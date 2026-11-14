from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.client_store import ClientStore
from backend.main import create_app
from backend.project_commands import CommandProjectStore

TOKEN = "l53-company-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def make_api(tmp_path: Path) -> TestClient:
    clients = ClientStore(tmp_path / "clients.db")
    store = CommandProjectStore(root=tmp_path / "projects", client_store=clients)
    return TestClient(
        create_app(TOKEN, allow_test_host=True, project_store=store, client_store=clients)
    )


def company_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "legal_name": "ACME Énergie",
        "trade_name": "ACME",
        "address_line1": "12 rue de l'Électricité",
        "address_line2": "Bâtiment B",
        "postal_code": "75000",
        "city": "Paris",
        "country": "France",
        "phone": "+33 1 23 45 67 89",
        "email": "contact@acme.example",
        "website": "https://acme.example",
        "siren": "123456789",
        "siret": "12345678900012",
        "vat_number": "FR12345678901",
        "manager_name": "Jeanne Dupont",
        "manager_role": "Présidente",
        "document_footer": "ACME Énergie — document interne",
    }
    payload.update(overrides)
    return payload


def test_empty_company_is_not_created_and_has_no_default_identity(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        response = api.get("/api/company", headers=AUTH)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["configured"] is False
        assert body["company"]["legal_name"] == ""
        assert body["company"]["logo"] is None
    import sqlite3

    connection = sqlite3.connect(tmp_path / "clients.db")
    try:
        assert connection.execute("SELECT COUNT(*) FROM company_profile").fetchone()[0] == 0
    finally:
        connection.close()


def test_company_create_update_singleton_and_restart(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        created = api.put("/api/company", headers=AUTH, json=company_payload())
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["configured"] is True
        assert body["company"]["legal_name"] == "ACME Énergie"
        assert body["company"]["siren"] == "123456789"
        updated = api.put(
            "/api/company",
            headers=AUTH,
            json=company_payload(phone="+33 9 99 99 99 99"),
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["company"]["phone"] == "+33 9 99 99 99 99"
    with make_api(tmp_path) as api:
        body = api.get("/api/company", headers=AUTH).json()
        assert body["configured"] is True
        assert body["company"]["legal_name"] == "ACME Énergie"
        assert body["company"]["phone"] == "+33 9 99 99 99 99"
    import sqlite3

    connection = sqlite3.connect(tmp_path / "clients.db")
    try:
        assert connection.execute("SELECT COUNT(*) FROM company_profile").fetchone()[0] == 1
    finally:
        connection.close()


def test_company_validation_optional_legal_identifiers(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        missing = api.put("/api/company", headers=AUTH, json=company_payload(legal_name=""))
        assert missing.status_code == 422
        assert missing.json()["code"] == "COMPANY_CHAMP_OBLIGATOIRE"
        invalid_values = {
            "siren": "123",
            "siret": "123",
            "vat_number": "1",
            "email": "invalide",
            "website": "invalide",
        }
        for field, invalid in invalid_values.items():
            response = api.put(
                "/api/company", headers=AUTH, json=company_payload(**{field: invalid})
            )
            assert response.status_code == 422, (field, response.text)
        empty_legal = api.put(
            "/api/company",
            headers=AUTH,
            json=company_payload(siren="", siret="", vat_number=""),
        )
        assert empty_legal.status_code == 200, empty_legal.text


def test_company_logo_upload_read_replace_delete(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        assert api.put("/api/company", headers=AUTH, json=company_payload()).status_code == 200
        image = BytesIO()
        Image.new("RGB", (8, 8), "white").save(image, format="PNG")
        png = image.getvalue()
        uploaded = api.post(
            "/api/company/logo",
            headers={**AUTH, "Content-Type": "image/png"},
            content=png,
        )
        assert uploaded.status_code == 200, uploaded.text
        assert uploaded.json()["company"]["logo"]
        fetched = api.get("/api/company/logo", headers=AUTH)
        assert fetched.status_code == 200
        assert fetched.content == png
        invalid = api.post(
            "/api/company/logo",
            headers={**AUTH, "Content-Type": "image/png"},
            content=b"not-an-image",
        )
        assert invalid.status_code == 422
        removed = api.delete("/api/company/logo", headers=AUTH)
        assert removed.status_code == 200, removed.text
        assert removed.json()["company"]["logo"] is None
        assert api.get("/api/company/logo", headers=AUTH).status_code == 404


def test_logo_requires_configured_company(tmp_path: Path) -> None:
    with make_api(tmp_path) as api:
        image = BytesIO()
        Image.new("RGB", (4, 4), "black").save(image, format="PNG")
        response = api.post(
            "/api/company/logo",
            headers={**AUTH, "Content-Type": "image/png"},
            content=image.getvalue(),
        )
        assert response.status_code == 422
        assert response.json()["code"] == "COMPANY_NON_CONFIGUREE"
