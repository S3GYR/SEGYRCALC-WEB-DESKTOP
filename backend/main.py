"""FastAPI loopback service for the isolated SEGYRCALC WEB-01 prototype."""

from __future__ import annotations

import json
import secrets
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .client_store import ClientStore, ClientStoreError
from .company_store import CompanyStore, CompanyStoreError
from .project_commands import CommandProjectStore
from .project_store import ProjectStoreError
from .reporting import ReportConfig, ReportService
from .runtime_paths import logs_root

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
TOKEN_HEADER = "x-segyr-token"
MAX_API_BODY_BYTES = 16_384
MAX_LOGO_BODY_BYTES = 5 * 1024 * 1024 + 4_096
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


class PowerRequest(BaseModel):
    mode: Literal["P_KNOWN", "S_KNOWN"] = "P_KNOWN"
    network: Literal["MONO", "TRI"] = "TRI"
    voltage_v: str = Field(min_length=1, max_length=32)
    power_value: str = Field(min_length=1, max_length=32)
    power_unit: str = Field(min_length=1, max_length=8)
    power_factor: str = Field(min_length=1, max_length=32)
    power_nature: Literal["ABSORBED", "USEFUL"] = "ABSORBED"
    efficiency: str | None = Field(default=None, max_length=32)


class ClientCreateRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    address: str = Field(default="", max_length=500)
    address_line1: str = Field(default="", max_length=200)
    address_line2: str = Field(default="", max_length=200)
    postal_code: str = Field(default="", max_length=20)
    city: str = Field(default="", max_length=120)
    country: str = Field(default="", max_length=100)
    contact_name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=60)
    allow_duplicate: bool = False


class ClientUpdateRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    address: str = Field(default="", max_length=500)
    address_line1: str = Field(default="", max_length=200)
    address_line2: str = Field(default="", max_length=200)
    postal_code: str = Field(default="", max_length=20)
    city: str = Field(default="", max_length=120)
    country: str = Field(default="", max_length=100)
    contact_name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=60)
    allow_duplicate: bool = False


class CompanyUpdateRequest(BaseModel):
    legal_name: str = Field(default="", max_length=200)
    trade_name: str = Field(default="", max_length=200)
    address_line1: str = Field(default="", max_length=200)
    address_line2: str = Field(default="", max_length=200)
    postal_code: str = Field(default="", max_length=20)
    city: str = Field(default="", max_length=120)
    country: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=254)
    website: str = Field(default="", max_length=300)
    siren: str = Field(default="", max_length=20)
    siret: str = Field(default="", max_length=25)
    vat_number: str = Field(default="", max_length=30)
    manager_name: str = Field(default="", max_length=200)
    manager_role: str = Field(default="", max_length=200)
    document_footer: str = Field(default="", max_length=1000)


class NewProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    reference: str = Field(min_length=1, max_length=200)
    client: str = Field(default="", max_length=500)
    client_id: str | None = Field(default=None, max_length=64)
    site: str = Field(default="", max_length=500)
    address: str = Field(default="", max_length=500)
    author: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4000)
    observations: str = Field(default="", max_length=4000)
    revision: str = Field(default="A", max_length=20)
    standard: str = Field(default="NF C 15-100", max_length=100)
    network: Literal["MONO", "TRI"] = "TRI"
    voltage_v: str = Field(default="400", min_length=1, max_length=32)
    has_neutral: bool = True
    voltage_ln_v: str | None = Field(default="230", max_length=32)


class SourceUpdateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    source: dict[str, Any] | None = None


class GeneralInfoRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=500)
    reference: str = Field(min_length=1, max_length=200)
    client: str = Field(default="", max_length=500)
    client_id: str | None = Field(default=None, max_length=64)
    detach_client: bool = False
    refresh_client: bool = False
    site: str = Field(default="", max_length=500)
    address: str = Field(default="", max_length=500)
    author: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4000)
    observations: str = Field(default="", max_length=4000)
    revision: str = Field(default="A", max_length=20)
    standard: str = Field(default="NF C 15-100", max_length=100)


class OpenProjectRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class SaveProjectRequest(BaseModel):
    path: str | None = Field(default=None, max_length=4096)
    overwrite: bool = False


class BoardCreateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    parent_board_id: str = Field(min_length=1, max_length=100)
    board_id: str | None = Field(default=None, max_length=100)
    designation: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=4000)
    has_neutral: bool = False
    voltage_ln_v: str | None = Field(default=None, max_length=32)


class BoardUpdateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    designation: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=4000)
    has_neutral: bool = False
    voltage_ln_v: str | None = Field(default=None, max_length=32)


class FeederCreateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    parent_board_id: str = Field(min_length=1, max_length=100)
    feeder_id: str | None = Field(default=None, max_length=100)
    reference: str | None = Field(default=None, max_length=50)
    auto_reference: bool = False
    designation: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=4000)
    ks: str | None = Field(default=None, max_length=32)
    distribution_type: Literal["MONO_N", "TRI_NO_N", "TRI_N"] | None = None
    network: Literal["MONO", "TRI"] | None = None
    voltage_v: str | None = Field(default=None, max_length=32)
    phase: str | None = Field(default=None, max_length=8)
    has_neutral: bool | None = None
    voltage_ln_v: str | None = Field(default=None, max_length=32)


class FeederWithLoadCreateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    parent_board_id: str = Field(min_length=1, max_length=100)
    feeder: dict[str, Any]
    load: dict[str, Any]


class FeederUpdateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    reference: str | None = Field(default=None, max_length=50)
    auto_reference: bool = False
    designation: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=4000)
    ks: str | None = Field(default=None, max_length=32)
    distribution_type: Literal["MONO_N", "TRI_NO_N", "TRI_N"] | None = None
    network: Literal["MONO", "TRI"] | None = None
    voltage_v: str | None = Field(default=None, max_length=32)
    phase: str | None = Field(default=None, max_length=8)
    has_neutral: bool | None = None
    voltage_ln_v: str | None = Field(default=None, max_length=32)


class LoadCreateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    feeder_id: str = Field(min_length=1, max_length=100)
    load_id: str | None = Field(default=None, max_length=100)
    designation: str = Field(min_length=1, max_length=500)
    network: Literal["MONO", "TRI"] = "MONO"
    voltage_v: str = Field(default="230", min_length=1, max_length=32)
    nominal_power: str = Field(min_length=1, max_length=32)
    power_unit: Literal["W", "kW"] = "W"
    quantity: int = Field(default=1, ge=1, le=100000)
    power_factor: str = Field(default="0.9", min_length=1, max_length=32)
    ku: str = Field(default="1", min_length=1, max_length=32)
    phase: str | None = Field(default=None, max_length=8)


class LoadUpdateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    feeder_id: str | None = Field(default=None, max_length=100)
    designation: str = Field(min_length=1, max_length=500)
    network: Literal["MONO", "TRI"] = "MONO"
    voltage_v: str = Field(default="230", min_length=1, max_length=32)
    nominal_power: str = Field(min_length=1, max_length=32)
    power_unit: Literal["W", "kW"] = "W"
    quantity: int = Field(default=1, ge=1, le=100000)
    power_factor: str = Field(default="0.9", min_length=1, max_length=32)
    ku: str = Field(default="1", min_length=1, max_length=32)
    phase: str | None = Field(default=None, max_length=8)


class MoveBoardRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    board_id: str | None = Field(default=None, max_length=100)
    destination_board_id: str = Field(min_length=1, max_length=100)


class DuplicateBoardRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    board_id: str | None = Field(default=None, max_length=100)
    destination_board_id: str | None = Field(default=None, max_length=100)


class MoveFeederRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    feeder_id: str | None = Field(default=None, max_length=100)
    destination_board_id: str = Field(min_length=1, max_length=100)


class DuplicateFeederRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    feeder_id: str | None = Field(default=None, max_length=100)
    destination_board_id: str | None = Field(default=None, max_length=100)


class MoveLoadRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    load_id: str | None = Field(default=None, max_length=100)
    destination_feeder_id: str = Field(min_length=1, max_length=100)


class DuplicateLoadRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    load_id: str | None = Field(default=None, max_length=100)
    destination_feeder_id: str | None = Field(default=None, max_length=100)


class UndoRedoRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class ClientDiagnosticRequest(BaseModel):
    event: str = Field(min_length=1, max_length=100)
    time: float = 0
    data: dict[str, Any] = Field(default_factory=dict)


class ReportConfigRequest(BaseModel):
    title: str = Field(default="Bilan de puissance électrique", min_length=1, max_length=200)
    sections: list[str] = Field(
        default_factory=lambda: [
            "cover",
            "general",
            "summary",
            "architecture",
            "boards",
            "feeders",
            "receivers",
            "coefficients",
            "phases",
            "assumptions",
            "traceability",
        ]
    )
    orientation: Literal["portrait", "landscape"] = "portrait"
    decimals: int = Field(default=2, ge=0, le=6)
    units: str = Field(default="auto", max_length=16)
    csv_delimiter: Literal[";", ",", "\t"] = ";"
    include_assumptions: bool = True
    include_traceability: bool = True


class ReportPreviewRequest(BaseModel):
    config: ReportConfigRequest = Field(default_factory=ReportConfigRequest)


class ReportExportRequest(BaseModel):
    snapshot_id: str = Field(min_length=1, max_length=100)
    format: Literal["pdf", "xlsx", "csv"]
    path: str = Field(min_length=1, max_length=4096)
    overwrite: bool = False


def _adapter():
    from . import engine_adapter

    return engine_adapter


def _store_response(operation):
    try:
        return operation()
    except ProjectStoreError as exc:
        return JSONResponse(
            {"detail": exc.message, "code": exc.code},
            status_code=exc.status_code,
        )
    except Exception as exc:
        return JSONResponse(
            {"detail": f"Opération projet impossible: {exc}", "code": "PROJET_OPERATION_ECHEC"},
            status_code=422,
        )


def _security_headers(response, *, api: bool, host: str) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    if api:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    else:
        response.headers["Cache-Control"] = (
            "no-store"
            if "text/html" in response.headers.get("content-type", "")
            else "public, max-age=3600"
        )
    response.headers["X-Local-Host"] = host


_DIAGNOSTIC_LOCK = threading.Lock()


def _append_diagnostic(name: str, payload: dict[str, Any]) -> None:
    try:
        root = logs_root()
        root.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {"received_at": datetime.now(UTC).isoformat(), **payload},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with _DIAGNOSTIC_LOCK, (root / f"{name}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        # Diagnostics must never affect the application.
        pass


def create_app(
    session_token: str | None = None,
    *,
    dist_dir: Path | None = None,
    allow_test_host: bool = False,
    project_store: CommandProjectStore | None = None,
    report_service: ReportService | None = None,
    client_store: ClientStore | None = None,
    company_store: CompanyStore | None = None,
) -> FastAPI:
    token = session_token or secrets.token_urlsafe(32)
    static_dir = (dist_dir or DIST_DIR) / "assets"
    allowed_hosts = ALLOWED_HOSTS | ({"testserver"} if allow_test_host else set())
    store = project_store or CommandProjectStore(client_store=client_store)
    if client_store is not None and store.client_store is None:
        store.client_store = client_store
    reports = report_service or ReportService()
    if company_store is None:
        base_client = client_store or store.client_store
        company_store = CompanyStore(base_client.db_path if base_client is not None else None)

    app = FastAPI(
        title="SEGYRCALC local prototype",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.session_token = token
    app.state.dist_dir = dist_dir or DIST_DIR
    app.state.project_store = store
    app.state.report_service = reports
    app.state.client_store = client_store
    app.state.company_store = company_store

    def _clients() -> ClientStore:
        current = app.state.client_store
        if current is None:
            current = ClientStore()
            app.state.client_store = current
            if store.client_store is None:
                store.client_store = current
        return current

    def _client_response(operation: Callable[[], Any]) -> Any:
        try:
            return operation()
        except ClientStoreError as exc:
            return JSONResponse(
                {"detail": exc.message, "code": exc.code},
                status_code=exc.status_code,
            )

    def _company() -> CompanyStore:
        current = app.state.company_store
        if current is None:
            base = _clients()
            current = CompanyStore(base.db_path)
            app.state.company_store = current
        return current

    def _company_response(operation: Callable[[], Any]) -> Any:
        try:
            return operation()
        except CompanyStoreError as exc:
            return JSONResponse(
                {"detail": exc.message, "code": exc.code},
                status_code=exc.status_code,
            )

    def _company_payload(profile: dict[str, Any]) -> dict[str, object]:
        return {
            "company": {key: value for key, value in profile.items() if key != "configured"},
            "configured": bool(profile.get("configured")),
        }

    if static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir), name="assets")

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        host = request.headers.get("host", "").lower()
        host_name = host.split(":")[0]
        if host_name not in allowed_hosts:
            return JSONResponse({"detail": "Hote non autorise."}, status_code=400)

        path = request.url.path
        if path.startswith("/api/"):
            length = request.headers.get("content-length")
            if length:
                try:
                    body_limit = (
                        MAX_LOGO_BODY_BYTES
                        if (path.startswith("/api/clients/") and path.endswith("/logo"))
                        or path == "/api/company/logo"
                        else MAX_API_BODY_BYTES
                    )
                    if int(length) > body_limit:
                        return JSONResponse(
                            {"detail": "Corps de requête trop volumineux."}, status_code=413
                        )
                except ValueError:
                    return JSONResponse(
                        {"detail": "Longueur de requête invalide."}, status_code=400
                    )

            supplied = request.headers.get(TOKEN_HEADER, "")
            if not supplied or not secrets.compare_digest(supplied, token):
                return JSONResponse({"detail": "Jeton de session local invalide."}, status_code=401)

            origin = request.headers.get("origin")
            if origin:
                expected_origin = f"http://{host}"
                if origin.rstrip("/") != expected_origin:
                    return JSONResponse({"detail": "Origine non autorisée."}, status_code=403)

            fetch_site = request.headers.get("sec-fetch-site")
            if fetch_site and fetch_site not in {"same-origin", "none"}:
                return JSONResponse(
                    {"detail": "Contexte de requête non autorisé."}, status_code=403
                )

        response = await call_next(request)
        _append_diagnostic("http-events", {"path": path, "status": response.status_code})
        _security_headers(response, api=path.startswith("/api/"), host=host)
        return response

    @app.exception_handler(Exception)
    async def unhandled_error(_request: Request, exc: Exception):  # pragma: no cover - defensive
        _ = exc
        return JSONResponse({"detail": "Erreur locale non divulguée."}, status_code=500)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        index_path = app.state.dist_dir / "index.html"
        if not index_path.is_file():
            return HTMLResponse(
                "<h1>Interface non construite</h1><p>Exécuter npm run build dans frontend/.</p>",
                status_code=503,
            )
        html = index_path.read_text(encoding="utf-8")
        if "__SEGYR_SESSION_TOKEN__" not in html:
            return HTMLResponse("Jeton de session non injectable.", status_code=503)
        return HTMLResponse(html.replace("__SEGYR_SESSION_TOKEN__", token))

    @app.get("/api/engine/info")
    async def engine_info() -> dict[str, object]:
        try:
            adapter = _adapter()
            return {
                "engine": {
                    "source": str(adapter.ENGINE_SRC),
                    "power_sha256": adapter.POWER_SOURCE_SHA256,
                    "project_sha256": adapter.PROJECT_SOURCE_SHA256,
                    "fixture": str(adapter.FIXTURE),
                    "facade": "calcelect.service_v13.calculate_project_v13",
                    "power_function": "segyr_calc.core.power.calculate_power",
                    "data_class": "REAL_ENGINE_FIXTURE",
                },
                "offline": True,
                "read_only": True,
            }
        except Exception as exc:
            return {"status": "engine_unavailable", "detail": str(exc)}

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        try:
            adapter = _adapter()
            return {
                "status": "ok",
                "offline": True,
                "api": "fastapi",
                "engine": {
                    "source": str(adapter.ENGINE_SRC),
                    "power_sha256": adapter.POWER_SOURCE_SHA256,
                    "project_sha256": adapter.PROJECT_SOURCE_SHA256,
                    "fixture": str(adapter.FIXTURE),
                },
                "docs_enabled": False,
            }
        except Exception as exc:
            return {
                "status": "engine_unavailable",
                "offline": True,
                "detail": str(exc),
                "docs_enabled": False,
            }

    @app.get("/api/clients", response_model=None)
    async def clients_list(
        search: str = "",
        include_archived: bool = True,
    ) -> dict[str, object] | JSONResponse:
        return _client_response(
            lambda: {
                "clients": _clients().list_clients(
                    search=search,
                    include_archived=include_archived,
                )
            }
        )

    @app.post("/api/clients", response_model=None)
    async def clients_create(payload: ClientCreateRequest) -> dict[str, object] | JSONResponse:
        return _client_response(lambda: _clients().create(payload.model_dump()))

    @app.get("/api/clients/{client_id}/projects", response_model=None)
    async def clients_projects(client_id: str) -> dict[str, object] | JSONResponse:
        def operation() -> dict[str, object]:
            client = _clients().get(client_id)
            projects = [
                item for item in store.list_files() if item.get("client_id") == client["id"]
            ]
            return {"client_id": client["id"], "projects": projects}

        return _client_response(operation)

    @app.get("/api/clients/{client_id}/logo", response_model=None)
    async def clients_logo_get(client_id: str):
        try:
            data, media_type = _clients().read_logo(client_id)
            return Response(
                content=data, media_type=media_type, headers={"Cache-Control": "no-store"}
            )
        except ClientStoreError as exc:
            return JSONResponse(
                {"detail": exc.message, "code": exc.code},
                status_code=exc.status_code,
            )

    @app.post("/api/clients/{client_id}/logo", response_model=None)
    async def clients_logo_set(
        client_id: str, request: Request
    ) -> dict[str, object] | JSONResponse:
        try:
            data = await request.body()
            return _client_response(lambda: _clients().set_logo(client_id, data))
        except ClientStoreError as exc:
            return JSONResponse(
                {"detail": exc.message, "code": exc.code},
                status_code=exc.status_code,
            )

    @app.delete("/api/clients/{client_id}/logo", response_model=None)
    async def clients_logo_delete(client_id: str) -> dict[str, object] | JSONResponse:
        return _client_response(lambda: _clients().remove_logo(client_id))

    @app.get("/api/clients/{client_id}", response_model=None)
    async def clients_get(client_id: str) -> dict[str, object] | JSONResponse:
        return _client_response(lambda: _clients().get(client_id))

    @app.put("/api/clients/{client_id}", response_model=None)
    async def clients_update(
        client_id: str,
        payload: ClientUpdateRequest,
    ) -> dict[str, object] | JSONResponse:
        return _client_response(lambda: _clients().update(client_id, payload.model_dump()))

    @app.post("/api/clients/{client_id}/archive", response_model=None)
    async def clients_archive(client_id: str) -> dict[str, object] | JSONResponse:
        return _client_response(lambda: _clients().archive(client_id))

    @app.post("/api/clients/{client_id}/reactivate", response_model=None)
    async def clients_reactivate(client_id: str) -> dict[str, object] | JSONResponse:
        return _client_response(lambda: _clients().reactivate(client_id))

    @app.get("/api/calculate/project", response_model=None)
    @app.get("/api/engine/project", response_model=None)
    async def engine_project() -> dict[str, object] | JSONResponse:
        try:
            return _adapter().load_project_payload()
        except Exception as exc:
            return JSONResponse({"detail": f"Moteur indisponible : {exc}"}, status_code=503)

    @app.post("/api/calculate/power", response_model=None)
    @app.post("/api/engine/power", response_model=None)
    async def engine_power(payload: PowerRequest) -> dict[str, object] | JSONResponse:
        try:
            return _adapter().calculate_power_payload(payload.model_dump())
        except Exception as exc:
            return JSONResponse(
                {"detail": f"Entrée ou moteur indisponible : {exc}"},
                status_code=422,
            )

    @app.get("/api/company", response_model=None)
    async def company_get() -> dict[str, object] | JSONResponse:
        return _company_response(lambda: _company_payload(_company().get()))

    @app.put("/api/company", response_model=None)
    async def company_update(payload: CompanyUpdateRequest) -> dict[str, object] | JSONResponse:
        return _company_response(lambda: _company_payload(_company().update(payload.model_dump())))

    @app.get("/api/company/logo", response_model=None)
    async def company_logo_get():
        try:
            data, media_type = _company().read_logo()
            return Response(
                content=data, media_type=media_type, headers={"Cache-Control": "no-store"}
            )
        except CompanyStoreError as exc:
            return JSONResponse(
                {"detail": exc.message, "code": exc.code}, status_code=exc.status_code
            )

    @app.post("/api/company/logo", response_model=None)
    async def company_logo_set(request: Request) -> dict[str, object] | JSONResponse:
        try:
            data = await request.body()
            return _company_response(lambda: _company_payload(_company().set_logo(data)))
        except CompanyStoreError as exc:
            return JSONResponse(
                {"detail": exc.message, "code": exc.code}, status_code=exc.status_code
            )

    @app.delete("/api/company/logo", response_model=None)
    async def company_logo_delete() -> dict[str, object] | JSONResponse:
        return _company_response(lambda: _company_payload(_company().remove_logo()))

    @app.get("/api/project/source", response_model=None)
    async def project_source_get() -> dict[str, object] | JSONResponse:
        def operation() -> dict[str, object]:
            payload = store._payload()
            return {
                "source": payload.get("source"),
                "format_version": payload.get("format_version"),
            }
        return _store_response(operation)

    @app.put("/api/project/source", response_model=None)
    async def project_source_put(payload: SourceUpdateRequest) -> dict[str, object] | JSONResponse:
        return _store_response(lambda: store.update_source(payload.model_dump()))

    @app.delete("/api/project/source", response_model=None)
    async def project_source_delete(expected_revision: int) -> dict[str, object] | JSONResponse:
        return _store_response(
            lambda: store.update_source(
                {"expected_revision": expected_revision, "source": None}
            )
        )

    @app.get("/api/project", response_model=None)
    async def project_current() -> dict[str, object] | JSONResponse:
        return _store_response(store._payload)

    @app.post("/api/project/new", response_model=None)
    async def project_new(payload: NewProjectRequest) -> dict[str, object] | JSONResponse:
        return _store_response(lambda: store.new(**payload.model_dump()))

    @app.post("/api/project/open", response_model=None)
    async def project_open(payload: OpenProjectRequest) -> dict[str, object] | JSONResponse:
        return _store_response(lambda: store.open(Path(payload.path)))

    @app.post("/api/project/save", response_model=None)
    async def project_save(payload: SaveProjectRequest) -> dict[str, object] | JSONResponse:
        path = Path(payload.path) if payload.path else None
        return _store_response(lambda: store.save(path, overwrite=payload.overwrite))

    @app.post("/api/project/save-as", response_model=None)
    async def project_save_as(payload: SaveProjectRequest) -> dict[str, object] | JSONResponse:
        if not payload.path:
            return JSONResponse(
                {"detail": "Chemin de sauvegarde requis.", "code": "CHEMIN_REQUIS"}, status_code=400
            )
        return _store_response(
            lambda: store.save_as(Path(payload.path), overwrite=payload.overwrite)
        )

    @app.post("/api/project/duplicate", response_model=None)
    async def project_duplicate(payload: SaveProjectRequest) -> dict[str, object] | JSONResponse:
        if not payload.path:
            return JSONResponse(
                {"detail": "Chemin de duplication requis.", "code": "CHEMIN_REQUIS"},
                status_code=400,
            )
        return _store_response(
            lambda: store.duplicate(Path(payload.path), overwrite=payload.overwrite)
        )

    @app.post("/api/project/close", response_model=None)
    async def project_close() -> dict[str, object] | JSONResponse:
        return _store_response(store.close)

    @app.post("/api/project/general", response_model=None)
    async def project_general(payload: GeneralInfoRequest) -> dict[str, object] | JSONResponse:
        return _store_response(lambda: store.update_general(payload.model_dump()))

    @app.get("/api/project/files", response_model=None)
    async def project_files() -> dict[str, object]:
        return {"files": store.list_files(), "root": str(store.root)}

    @app.post("/api/project/boards", response_model=None)
    async def project_add_board(payload: BoardCreateRequest) -> dict[str, object] | JSONResponse:
        return _store_response(lambda: store.add_board(payload.model_dump()))

    @app.put("/api/project/boards/{board_id}", response_model=None)
    async def project_update_board(
        board_id: str, payload: BoardUpdateRequest
    ) -> dict[str, object] | JSONResponse:
        data = payload.model_dump()
        data["board_id"] = board_id
        return _store_response(lambda: store.update_board(data))

    @app.delete("/api/project/boards/{board_id}", response_model=None)
    async def project_delete_board(
        board_id: str, expected_revision: int, cascade: bool = False
    ) -> dict[str, object] | JSONResponse:
        return _store_response(
            lambda: store.delete(
                "board",
                board_id,
                cascade=cascade,
                expected_revision=expected_revision,
            )
        )

    @app.post("/api/project/boards/{board_id}/move", response_model=None)
    async def project_move_board(
        board_id: str, payload: MoveBoardRequest
    ) -> dict[str, object] | JSONResponse:
        data = payload.model_dump()
        data["board_id"] = board_id
        return _store_response(lambda: store.move_board(data))

    @app.post("/api/project/boards/{board_id}/duplicate", response_model=None)
    async def project_duplicate_board(
        board_id: str, payload: DuplicateBoardRequest
    ) -> dict[str, object] | JSONResponse:
        data = payload.model_dump()
        data["board_id"] = board_id
        return _store_response(lambda: store.duplicate_board(data))

    @app.post("/api/project/feeders", response_model=None)
    async def project_add_feeder(payload: FeederCreateRequest) -> dict[str, object] | JSONResponse:
        return _store_response(lambda: store.add_feeder(payload.model_dump()))

    @app.post("/api/project/feeders-with-load", response_model=None)
    async def project_add_feeder_with_load(
        payload: FeederWithLoadCreateRequest,
    ) -> dict[str, object] | JSONResponse:
        return _store_response(lambda: store.add_feeder_with_load(payload.model_dump()))

    @app.put("/api/project/feeders/{feeder_id}", response_model=None)
    async def project_update_feeder(
        feeder_id: str, payload: FeederUpdateRequest
    ) -> dict[str, object] | JSONResponse:
        data = payload.model_dump()
        data["feeder_id"] = feeder_id
        return _store_response(lambda: store.update_feeder(data))

    @app.delete("/api/project/feeders/{feeder_id}", response_model=None)
    async def project_delete_feeder(
        feeder_id: str, expected_revision: int, cascade: bool = False
    ) -> dict[str, object] | JSONResponse:
        return _store_response(
            lambda: store.delete(
                "feeder",
                feeder_id,
                cascade=cascade,
                expected_revision=expected_revision,
            )
        )

    @app.post("/api/project/feeders/{feeder_id}/move", response_model=None)
    async def project_move_feeder(
        feeder_id: str, payload: MoveFeederRequest
    ) -> dict[str, object] | JSONResponse:
        data = payload.model_dump()
        data["feeder_id"] = feeder_id
        return _store_response(lambda: store.move_feeder(data))

    @app.post("/api/project/feeders/{feeder_id}/duplicate", response_model=None)
    async def project_duplicate_feeder(
        feeder_id: str, payload: DuplicateFeederRequest
    ) -> dict[str, object] | JSONResponse:
        data = payload.model_dump()
        data["feeder_id"] = feeder_id
        return _store_response(lambda: store.duplicate_feeder(data))

    @app.post("/api/project/loads", response_model=None)
    async def project_add_load(payload: LoadCreateRequest) -> dict[str, object] | JSONResponse:
        return _store_response(lambda: store.add_load(payload.model_dump()))

    @app.put("/api/project/loads/{load_id}", response_model=None)
    async def project_update_load(
        load_id: str, payload: LoadUpdateRequest
    ) -> dict[str, object] | JSONResponse:
        data = payload.model_dump()
        data["load_id"] = load_id
        return _store_response(lambda: store.update_load(data))

    @app.delete("/api/project/loads/{load_id}", response_model=None)
    async def project_delete_load(
        load_id: str, expected_revision: int, cascade: bool = False
    ) -> dict[str, object] | JSONResponse:
        return _store_response(
            lambda: store.delete(
                "load",
                load_id,
                cascade=cascade,
                expected_revision=expected_revision,
            )
        )

    @app.post("/api/project/loads/{load_id}/move", response_model=None)
    async def project_move_load(
        load_id: str, payload: MoveLoadRequest
    ) -> dict[str, object] | JSONResponse:
        data = payload.model_dump()
        data["load_id"] = load_id
        return _store_response(lambda: store.move_load(data))

    @app.post("/api/project/loads/{load_id}/duplicate", response_model=None)
    async def project_duplicate_load(
        load_id: str, payload: DuplicateLoadRequest
    ) -> dict[str, object] | JSONResponse:
        data = payload.model_dump()
        data["load_id"] = load_id
        return _store_response(lambda: store.duplicate_load(data))

    @app.get("/api/project/deletion-preview/{kind}/{entity_id}", response_model=None)
    async def project_deletion_preview(
        kind: str, entity_id: str
    ) -> dict[str, object] | JSONResponse:
        return _store_response(lambda: store.delete_preview(kind, entity_id))

    @app.post("/api/project/undo", response_model=None)
    async def project_undo(payload: UndoRedoRequest) -> dict[str, object] | JSONResponse:
        return _store_response(lambda: store.undo(payload.expected_revision))

    @app.post("/api/project/redo", response_model=None)
    async def project_redo(payload: UndoRedoRequest) -> dict[str, object] | JSONResponse:
        return _store_response(lambda: store.redo(payload.expected_revision))

    @app.post("/api/project/recalculate", response_model=None)
    async def project_recalculate() -> dict[str, object] | JSONResponse:
        return _store_response(store.recalculate)

    @app.post("/api/diagnostics/client", response_model=None)
    async def diagnostics_client(payload: ClientDiagnosticRequest) -> dict[str, object]:
        _append_diagnostic("client-events", payload.model_dump())
        return {"ok": True}

    @app.get("/api/reports/options", response_model=None)
    async def reports_options() -> dict[str, object]:
        return {
            "sections": [
                {"id": "cover", "label": "Page de garde"},
                {"id": "general", "label": "Informations générales"},
                {"id": "summary", "label": "Synthèse générale TGBT"},
                {"id": "architecture", "label": "Architecture électrique"},
                {"id": "boards", "label": "Synthèses des tableaux"},
                {"id": "feeders", "label": "Bilan des départs"},
                {"id": "receivers", "label": "Bilan des récepteurs"},
                {"id": "coefficients", "label": "Coefficients Ku et Ks"},
                {"id": "phases", "label": "Répartition des phases"},
                {"id": "assumptions", "label": "Hypothèses et limites"},
                {"id": "traceability", "label": "Traçabilité"},
            ],
            "orientations": ["portrait", "landscape"],
            "formats": ["pdf", "xlsx", "csv"],
            "export_root": str(reports.root),
        }

    @app.post("/api/reports/preview", response_model=None)
    async def reports_preview(payload: ReportPreviewRequest) -> dict[str, object] | JSONResponse:
        return _store_response(
            lambda: reports.preview(
                store,
                ReportConfig.from_dict(payload.config.model_dump()),
            )
        )

    @app.post("/api/reports/export", response_model=None)
    async def reports_export(payload: ReportExportRequest) -> dict[str, object] | JSONResponse:
        return _store_response(
            lambda: reports.export(
                payload.snapshot_id,
                payload.format,
                Path(payload.path),
                overwrite=payload.overwrite,
            )
        )

    @app.get("/api/reports/exports", response_model=None)
    async def reports_exports() -> dict[str, object]:
        return {"root": str(reports.root), "files": reports.list_exports()}

    return app


app = create_app()
