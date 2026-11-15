from __future__ import annotations

import hashlib
import json
import shutil
import time
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.project_catalog import CatalogError, ProjectCatalog, normalize_search
from backend.project_commands import CommandProjectStore

TOKEN = "r6-3-a-test-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def write_project(
    root: Path,
    filename: str,
    *,
    name: str,
    reference: str = "",
    client_id: str | None = None,
    client_name: str = "",
    description: str = "",
    progress: str = "NOT_DEFINED",
    created_at: str | None = "2026-01-01T00:00:00+00:00",
    updated_at: str | None = "2026-01-02T00:00:00+00:00",
    project_id: str | None = None,
) -> Path:
    metadata: dict[str, object] = {
        "designation": name,
        "code": reference,
        "client_id": client_id,
        "progress": progress,
    }
    if created_at is not None:
        metadata["created_at"] = created_at
    if updated_at is not None:
        metadata["updated_at"] = updated_at
    payload = {
        "schema": "SEGYRCALC_WEB_PROJECT",
        "schema_version": "0.3.0",
        "web": {
            "site": "",
            "address": "",
            "observations": "",
            "created_by": "R6.3-A",
            "application": "SEGYRCALC Web Desktop",
            "format_version": "0.3.0",
        },
        "calcelect_v14": {
            "schema": "SEGYRCALC_CALCELECT",
            "schema_version": "1.4",
            "project": {
                "project_id": project_id or f"pid-{filename}",
                "metadata": metadata,
                "client_snapshot": {
                    "client_id": client_id,
                    "company_name": client_name,
                    "contact_name": "",
                    "address": "",
                    "phone": "",
                    "email": "",
                    "country": "",
                    "logo": None,
                    "captured_at": None,
                },
                "electrical": {
                    "project_id": project_id or f"pid-{filename}",
                    "name": name,
                    "reference": reference,
                    "description": description,
                    "client": client_name,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "boards": [],
                    "feeders": [],
                    "loads": [],
                    "legacy_groups": [],
                    "engine_version": "1.5",
                },
                "source": None,
            },
        },
    }
    path = root / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def catalog_for(root: Path) -> ProjectCatalog:
    return ProjectCatalog(root, [root])


def test_normalization_and_search_fields() -> None:
    assert normalize_search("Électricité") == "electricite"
    assert normalize_search("  Étude   TGBT  ") == "etude tgbt"
    assert normalize_search("CHANTIER") == "chantier"


def test_catalog_search_is_case_and_accent_insensitive_across_four_fields(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        "elec.segyrcalc-web.json",
        name="Électricité TGBT",
        reference="AFF-ELEC-01",
        client_name="Société Générale",
        description="Étude éclairage bâtiment",
    )
    write_project(
        tmp_path,
        "chantier.segyrcalc-web.json",
        name="Chantier Nord",
        reference="AFF-CHA-02",
        client_name="Bâtiment Plus",
        description="Tableau divisionnaire",
    )
    catalog = catalog_for(tmp_path)

    assert catalog.query(q="electricite")["total"] == 1
    assert catalog.query(q="ÉLECTRICITÉ")["total"] == 1
    assert catalog.query(q="aff-elec")["total"] == 1
    assert catalog.query(q="societe")["total"] == 1
    assert catalog.query(q="etude eclairage")["total"] == 1
    assert catalog.query(q="batiment")["total"] == 2
    assert catalog.query(q="tableau")["total"] == 1
    assert catalog.query(q="inconnu")["total"] == 0


def test_catalog_filters_client_progress_and_date(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        "c1-a.segyrcalc-web.json",
        name="Projet C1 A",
        client_id="client-1",
        client_name="Client Un",
        progress="IN_PROGRESS",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-10T00:00:00+00:00",
    )
    write_project(
        tmp_path,
        "c1-b.segyrcalc-web.json",
        name="Projet C1 B",
        client_id="client-1",
        client_name="Client Un",
        progress="COMPLETED",
        created_at="2026-02-01T00:00:00+00:00",
        updated_at="2026-02-10T00:00:00+00:00",
    )
    write_project(
        tmp_path,
        "c2.segyrcalc-web.json",
        name="Projet C2",
        client_id="client-2",
        client_name="Client Un",
        progress="NOT_DEFINED",
        created_at="2026-03-01T00:00:00+00:00",
        updated_at="2026-03-10T00:00:00+00:00",
    )
    write_project(
        tmp_path,
        "snapshot.segyrcalc-web.json",
        name="Projet historique",
        client_name="Client Snapshot",
        progress="NOT_DEFINED",
        created_at=None,
        updated_at=None,
    )
    catalog = catalog_for(tmp_path)

    assert catalog.query(client_id="client-1")["total"] == 2
    assert catalog.query(client_id="client-2")["total"] == 1
    assert catalog.query(client_id="absent")["total"] == 0
    assert catalog.query(progress="NOT_DEFINED")["total"] == 2
    assert catalog.query(progress="IN_PROGRESS")["total"] == 1
    assert catalog.query(progress="COMPLETED")["total"] == 1

    # Missing metadata dates are excluded from a date-filtered result, not invented.
    assert catalog.query(date_field="updated", date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))["total"] == 1
    assert catalog.query(date_field="created", date_from=date(2026, 1, 1), date_to=date(2026, 2, 28))["total"] == 2
    assert catalog.query(date_field="updated", date_from=date(2026, 1, 1), date_to=date(2026, 12, 31))["total"] == 3


def test_catalog_stable_sorts_and_pagination(tmp_path: Path) -> None:
    for index in range(120):
        write_project(
            tmp_path,
            f"p{index:03d}.segyrcalc-web.json",
            name=f"Projet {index:03d}",
            reference=f"REF-{index:03d}",
            client_name=f"Client {index % 3}",
            progress="IN_PROGRESS" if index % 2 else "COMPLETED",
            created_at=f"2026-01-{(index % 28) + 1:02d}T00:00:00+00:00",
            updated_at=f"2026-02-{(index % 28) + 1:02d}T00:00:00+00:00",
        )
    catalog = catalog_for(tmp_path)

    page_25 = catalog.query(sort="name_asc", page=1, page_size=25)
    assert len(page_25["items"]) == 25
    assert page_25["total"] == 120
    assert page_25["total_pages"] == 5
    assert page_25["has_next"] is True
    assert page_25["has_previous"] is False
    assert [item["name"] for item in page_25["items"]] == [f"Projet {index:03d}" for index in range(25)]

    page_50 = catalog.query(sort="name_asc", page=2, page_size=50)
    assert len(page_50["items"]) == 50
    assert page_50["items"][0]["name"] == "Projet 050"
    assert page_50["has_previous"] is True

    page_100 = catalog.query(sort="name_asc", page=2, page_size=100)
    assert len(page_100["items"]) == 20
    assert page_100["has_next"] is False

    out_of_range = catalog.query(sort="name_asc", page=99, page_size=25)
    assert out_of_range["items"] == []
    assert out_of_range["total"] == 120
    assert out_of_range["has_previous"] is True

    descending = catalog.query(sort="name_desc", page=1, page_size=25)
    assert descending["items"][0]["name"] == "Projet 119"
    assert [item["catalog_id"] for item in page_25["items"]] == [
        item["catalog_id"] for item in catalog.query(sort="name_asc", page=1, page_size=25)["items"]
    ]


def test_catalog_1000_projects_and_no_silent_limit(tmp_path: Path) -> None:
    for index in range(1000):
        write_project(
            tmp_path,
            f"batch-{index:04d}.segyrcalc-web.json",
            name=f"Projet volumétrie {index:04d}",
            reference=f"VOL-{index:04d}",
            client_name=f"Client {index % 10}",
        )
    catalog = catalog_for(tmp_path)

    started = time.perf_counter()
    result = catalog.query(page=1, page_size=100)
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert result["total"] == 1000
    assert result["total_pages"] == 10
    assert len(result["items"]) == 100
    assert elapsed_ms >= 0

    search_started = time.perf_counter()
    search = catalog.query(q="volumetrie 0999", page=1, page_size=25)
    search_ms = (time.perf_counter() - search_started) * 1000
    assert search["total"] == 1
    assert search["items"][0]["reference"] == "VOL-0999"
    assert search_ms >= 0

    # The test intentionally records timings for the qualification report without
    # imposing a machine-specific pass/fail threshold in the unit suite.
    assert result["items"][0]["name"].startswith("Projet volumétrie")


def test_corrupt_file_is_listed_without_exposing_path_and_does_not_stop_catalog(tmp_path: Path) -> None:
    (tmp_path / "corrupt.segyrcalc-web.json").write_text("{not-json", encoding="utf-8")
    write_project(tmp_path, "valid.segyrcalc-web.json", name="Projet valide")
    catalog = catalog_for(tmp_path)
    result = catalog.query(page=1, page_size=25)
    assert result["total"] == 2
    corrupt = next(item for item in result["items"] if item["metadata_error"])
    assert "path" not in corrupt
    assert "root" not in corrupt
    assert str(tmp_path) not in json.dumps(corrupt, ensure_ascii=False)
    assert corrupt["name"] == "corrupt.segyrcalc-web.json"


def test_catalog_does_not_write_project_files(tmp_path: Path) -> None:
    paths = [
        write_project(tmp_path, f"read-{index}.segyrcalc-web.json", name=f"Projet {index}")
        for index in range(12)
    ]
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    catalog = catalog_for(tmp_path)
    catalog.query(q="projet", page=1, page_size=100)
    catalog.query(sort="client_asc", page=1, page_size=100)
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert before == after


def test_catalog_rejects_unknown_sort_page_size_and_inverted_dates(tmp_path: Path) -> None:
    catalog = catalog_for(tmp_path)
    with pytest.raises(CatalogError):
        catalog.query(sort="unknown")
    with pytest.raises(CatalogError):
        catalog.query(page_size=30)  # type: ignore[arg-type]
    with pytest.raises(CatalogError):
        catalog.query(date_from=date(2026, 2, 1), date_to=date(2026, 1, 1))


def test_catalog_ignores_symlinked_project_when_supported(tmp_path: Path) -> None:
    source = write_project(tmp_path, "real.segyrcalc-web.json", name="Projet réel")
    link = tmp_path / "linked.segyrcalc-web.json"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("La création de lien symbolique n'est pas autorisée sur cette machine.")
    catalog = catalog_for(tmp_path)
    result = catalog.query(page=1, page_size=25)
    assert result["total"] == 1
    assert result["items"][0]["name"] == "Projet réel"


def test_catalog_resolve_uses_opaque_identifier(tmp_path: Path) -> None:
    path = write_project(tmp_path, "opaque.segyrcalc-web.json", name="Projet opaque")
    catalog = catalog_for(tmp_path)
    item = catalog.query()["items"][0]
    assert item["catalog_id"] != str(path)
    assert catalog.resolve(item["catalog_id"]) == path
    with pytest.raises(CatalogError):
        catalog.resolve("../opaque.segyrcalc-web.json")


def test_legacy_project_format_is_readable_without_full_electrical_model(tmp_path: Path) -> None:
    legacy = {
        "schema": "SEGYRCALC_CALCELECT",
        "schema_version": "1.3",
        "project": {
            "name": "Ancien projet",
            "reference": "V13-001",
            "description": "Projet historique",
            "client": "Client historique",
            "created_at": "2025-01-01T00:00:00+00:00",
            "updated_at": "2025-01-02T00:00:00+00:00",
        },
    }
    (tmp_path / "legacy.calcelect-v1.3.json").write_text(
        json.dumps(legacy, ensure_ascii=False), encoding="utf-8"
    )
    result = catalog_for(tmp_path).query(q="historique", page=1, page_size=25)
    assert result["total"] == 1
    item = result["items"][0]
    assert item["name"] == "Ancien projet"
    assert item["reference"] == "V13-001"
    assert item["format"] == "V1.3"
    assert item["client_name"] == "Client historique"
    assert item["progress"] == "NOT_DEFINED"


def test_catalog_api_contract_and_validation(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    root.mkdir()
    write_project(root, "api-one.segyrcalc-web.json", name="Projet API un", reference="API-001")
    store = CommandProjectStore(root=root)
    with TestClient(create_app(TOKEN, allow_test_host=True, project_store=store)) as api:
        response = api.get("/api/projects", headers=AUTH, params={"q": "api un", "page_size": 25})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert set(payload) == {"items", "page", "page_size", "total", "total_pages", "has_next", "has_previous"}
        assert payload["page_size"] == 25
        assert payload["items"]
        assert "path" not in payload["items"][0]
        assert "root" not in payload
        assert str(root) not in response.text

        assert api.get("/api/projects?page_size=30", headers=AUTH).status_code == 422
        assert api.get("/api/projects?sort=unknown", headers=AUTH).status_code == 422
        assert api.get(
            "/api/projects?date_from=2026-02-01&date_to=2026-01-01",
            headers=AUTH,
        ).status_code == 422
        assert api.post("/api/projects/not-a-catalog-id/open", headers=AUTH).status_code == 404

        invalid = api.get(
            "/api/projects",
            headers=AUTH,
            params={"q": "x" * 201},
        )
        assert invalid.status_code == 422


def test_catalog_api_opens_the_same_project_by_opaque_id(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    root.mkdir()
    sample = (
        Path(__file__).resolve().parents[2]
        / "packaging"
        / "sample_projects"
        / "web05-native-qualification.segyrcalc-web.json"
    )
    if not sample.is_file():
        pytest.skip("Le projet WEB-05 de qualification est absent.")
    shutil.copy2(sample, root / "web05-copy.segyrcalc-web.json")
    store = CommandProjectStore(root=root)
    with TestClient(create_app(TOKEN, allow_test_host=True, project_store=store)) as api:
        catalog = api.get("/api/projects", headers=AUTH, params={"q": "WEB05"}).json()
        item = next(item for item in catalog["items"] if item["name"] == "Bilan natif WEB-05")
        opened = api.post(f"/api/projects/{item['catalog_id']}/open", headers=AUTH)
        assert opened.status_code == 200, opened.text
        assert opened.json()["project"]["reference"] == "WEB05-NATIF"
        assert opened.json()["state"]["read_only_source"] is False


def test_list_files_no_longer_has_a_50_file_cap(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    root.mkdir()
    for index in range(60):
        (root / f"listing-{index:03d}.segyrcalc-web.json").write_text("{}", encoding="utf-8")
    store = CommandProjectStore(root=root)
    files = store.list_files()
    names = {item["name"] for item in files}
    assert len(files) >= 60
    assert all(f"listing-{index:03d}.segyrcalc-web.json" in names for index in range(60))
