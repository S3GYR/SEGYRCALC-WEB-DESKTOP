from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import create_app

TOKEN = "test-session-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def client() -> TestClient:
    return TestClient(create_app(TOKEN, allow_test_host=True))


def test_index_injects_session_token() -> None:
    response = client().get("/")
    assert response.status_code == 200
    assert TOKEN in response.text
    assert "__SEGYR_SESSION_TOKEN__" not in response.text
    assert "SEGYRCALC" in response.text
    assert "Content-Security-Policy" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"


def test_test_host_is_rejected_in_runtime_mode() -> None:
    with TestClient(create_app(TOKEN)) as api:
        response = api.get("/api/health", headers=AUTH)
    assert response.status_code == 400
    assert "non autoris" in response.json()["detail"]


def test_api_requires_token() -> None:
    with client() as api:
        response = api.get("/api/engine/project")
    assert response.status_code == 401
    assert "Jeton" in response.json()["detail"]


def test_docs_are_disabled() -> None:
    with client() as api:
        assert api.get("/docs").status_code == 404
        assert api.get("/openapi.json").status_code == 404
        assert api.get("/redoc").status_code == 404


def test_origin_and_fetch_metadata_are_checked() -> None:
    with client() as api:
        bad_origin = api.get(
            "/api/engine/project",
            headers={**AUTH, "Origin": "http://evil.example"},
        )
        assert bad_origin.status_code == 403
        bad_site = api.get(
            "/api/engine/project",
            headers={**AUTH, "Sec-Fetch-Site": "cross-site"},
        )
        assert bad_site.status_code == 403
        same_origin = api.get(
            "/api/engine/project",
            headers={**AUTH, "Origin": "http://testserver"},
        )
        assert same_origin.status_code == 200


def test_no_cors_header() -> None:
    with client() as api:
        response = api.get("/api/health", headers=AUTH)
    assert response.status_code == 200
    assert "access-control-allow-origin" not in {key.lower() for key in response.headers}


def test_body_size_is_bounded() -> None:
    with client() as api:
        response = api.post(
            "/api/engine/power",
            content=b"x" * 20_000,
            headers={**AUTH, "Content-Type": "application/json"},
        )
    assert response.status_code == 413


def test_real_power_engine_call() -> None:
    with client() as api:
        response = api.post(
            "/api/engine/power",
            headers=AUTH,
            json={
                "mode": "P_KNOWN",
                "network": "TRI",
                "voltage_v": "400",
                "power_value": "8000",
                "power_unit": "W",
                "power_factor": "0.8",
                "power_nature": "ABSORBED",
                "efficiency": None,
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OK"
    assert payload["p_abs_w"] == "8000"
    assert payload["q_var"] == "6000"
    assert payload["s_va"] == "10000"
    assert payload["current_a"].startswith("14.433756729740644112")
    assert payload["engine"]["function"] == "segyr_calc.core.power.calculate_power"
    assert len(payload["engine"]["source_sha256"]) == 64


def test_invalid_power_factor_is_reported_by_the_engine() -> None:
    with client() as api:
        response = api.post(
            "/api/engine/power",
            headers=AUTH,
            json={
                "mode": "P_KNOWN",
                "network": "TRI",
                "voltage_v": "400",
                "power_value": "8000",
                "power_unit": "W",
                "power_factor": "1.5",
                "power_nature": "ABSORBED",
                "efficiency": None,
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ERREUR"
    assert payload["diagnostics"][0]["code"] == "FACTEUR_PUISSANCE_INVALIDE"


def test_unparseable_efficiency_is_rejected() -> None:
    with client() as api:
        response = api.post(
            "/api/engine/power",
            headers=AUTH,
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


def test_real_project_engine_call() -> None:
    with client() as api:
        response = api.get("/api/engine/project", headers=AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert payload["project"]["load_count"] == 15
    assert payload["project"]["board_count"] == 3
    assert payload["project"]["feeder_count"] == 9
    assert payload["status"] == "OK"
    assert payload["engine"]["version"] == "1.3.0"
    assert payload["totals"]["p_installed_w"] == "55000"
    assert payload["totals"]["p_after_ks_w"] == "43240"
    assert len(payload["boards"]) == 3
    assert len(payload["feeders"]) == 9
    assert payload["boards"][0]["type"] == "TGBT"
    assert payload["feeders"][0]["current_phases"]["l1"] is not None


def test_project_payload_includes_real_loads() -> None:
    with client() as api:
        response = api.get("/api/engine/project", headers=AUTH)
    assert response.status_code == 200
    loads = response.json()["loads"]
    assert len(loads) == 15
    first = loads[0]
    assert first["id"] == "REC-01"
    assert first["parent_board_id"] == "TD-BUREAUX"
    assert first["feeder_id"] == "DEP-02"
    assert first["phase"] == "L1"
    assert first["installed_power_w"] == "1000"
    assert first["current_available"] is True
    assert first["apparent_power_available"] is True
    assert first["p_after_ks_w"] is not None
    assert first["s_after_ks_va"] is not None
    assert first["current_a"] is not None


def test_engine_info_and_aliases() -> None:
    with client() as api:
        info = api.get("/api/engine/info", headers=AUTH)
        project_alias = api.get("/api/calculate/project", headers=AUTH)
        power_alias = api.post(
            "/api/calculate/power",
            headers=AUTH,
            json={
                "mode": "P_KNOWN",
                "network": "TRI",
                "voltage_v": "400",
                "power_value": "8000",
                "power_unit": "W",
                "power_factor": "0.8",
                "power_nature": "ABSORBED",
                "efficiency": None,
            },
        )
    assert info.status_code == 200
    assert info.json()["read_only"] is True
    assert info.json()["engine"]["data_class"] == "REAL_ENGINE_FIXTURE"
    assert project_alias.status_code == 200
    assert power_alias.status_code == 200
    assert power_alias.json()["status"] == "OK"


def test_project_payload_exposes_engine_receiver_results() -> None:
    with client() as api:
        payload = api.get("/api/engine/project", headers=AUTH).json()
    for load in payload["loads"]:
        assert load["status"] in {"OK", "AVERTISSEMENT", "NON_CALCULABLE"}
        assert load["current_available"] is True
        assert load["apparent_power_available"] is True
        assert load["s_after_ks_va"] is not None
        assert load["current_a"] is not None


def test_health_exposes_offline_engine_metadata() -> None:
    with client() as api:
        response = api.get("/api/health", headers=AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["offline"] is True
    assert payload["docs_enabled"] is False
    assert len(payload["engine"]["power_sha256"]) == 64
