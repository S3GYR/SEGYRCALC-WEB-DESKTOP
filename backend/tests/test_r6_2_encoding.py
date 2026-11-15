"""R6.2 targeted regression tests for DEF-ENC-01 and DEF-ENC-02."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.project_commands import CommandProjectStore

ROOT = Path(__file__).resolve().parents[2]


def test_backend_sources_have_no_double_encoded_messages() -> None:
    main_source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "Opération projet impossible" in main_source
    assert "Entrée ou moteur indisponible" in main_source
    assert "\u00c3\u0192\u00c2" not in main_source


def test_project_messages_use_real_accents() -> None:
    store_source = (ROOT / "backend" / "project_store.py").read_text(encoding="utf-8")
    commands_source = (ROOT / "backend" / "project_commands.py").read_text(encoding="utf-8")

    assert "Le registre des repères de départs est invalide." in store_source
    assert "La source électrique est invalide" in store_source
    assert "Suppression de la source électrique" in commands_source
    assert "Modification de la source électrique" in commands_source

    for source in (store_source, commands_source):
        assert "rep?res" not in source
        assert "d?parts" not in source
        assert "?lectrique" not in source


def test_power_api_error_uses_clean_utf8(tmp_path: Path) -> None:
    store = CommandProjectStore(root=tmp_path / "projects")
    app = create_app(
        "r6-2-encoding-test-token",
        allow_test_host=True,
        project_store=store,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/engine/power",
            headers={"X-SEGYR-Token": "r6-2-encoding-test-token"},
            json={
                "mode": "P_KNOWN",
                "network": "TRI",
                "voltage_v": "400",
                "power_value": "8000",
                "power_unit": "W",
                "power_factor": "0.8",
                "power_nature": "USEFUL",
                "efficiency": "abc",
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert set(payload) == {"detail"}
    detail = payload["detail"]
    assert detail.startswith("Entrée ou moteur indisponible")
    assert "Ã" not in detail
    assert "\ufffd" not in detail
