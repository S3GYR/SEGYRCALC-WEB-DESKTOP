"""WEB-08 L5.1 client facade over the existing client database.

The SQLite database remains the client referential.  L5.1 adds the v2 schema
and enriched client fields, while the historical V1.4/V1.5 client package
continues to provide validation helpers and managed logo storage.  The
historical package itself is not modified.
"""

from __future__ import annotations

import mimetypes
import tempfile
import threading
from pathlib import Path
from typing import Any

from calcelect.clients.errors import (
    ClientError,
    ClientNotFoundError,
    ClientStorageError,
    ClientValidationError,
    DuplicateClientError,
    LogoValidationError,
)
from calcelect.clients.logos import LogoStore
from calcelect.clients.normalization import utc_now
from calcelect.project_v14 import ClientSnapshot

from .client_v2 import (
    MAX_LOGO_BYTES,
    ClientV2Record,
    ClientV2Repository,
    _connect,
)
from .runtime_paths import data_root


class ClientStoreError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _status_for(exc: ClientError) -> int:
    if isinstance(exc, DuplicateClientError):
        return 409
    if isinstance(exc, ClientNotFoundError):
        return 404
    if isinstance(exc, ClientStorageError):
        return 503
    if isinstance(exc, ClientValidationError):
        return 422
    if isinstance(exc, LogoValidationError):
        return 422
    return getattr(exc, "status_code", 422)


def _record_payload(record: ClientV2Record) -> dict[str, Any]:
    return {
        "id": record.id,
        "company_name": record.company_name,
        "address": record.address,
        "address_line1": record.address_line1,
        "address_line2": record.address_line2,
        "postal_code": record.postal_code,
        "city": record.city,
        "country": record.country,
        "contact_name": record.contact_name,
        "email": record.email,
        "phone": record.phone,
        "logo": record.logo,
        "has_logo": bool(record.logo),
        "formatted_address": record.formatted_address,
        "is_archived": record.is_archived,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _logo_mime(reference: str) -> str:
    suffix = Path(reference).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, mimetypes.guess_type(reference)[0] or "application/octet-stream")


class ClientStore:
    """Thread-safe client facade backed by the v2 client repository."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else data_root() / "data" / "clients.db"
        self.logo_root = self.db_path.parent / "logos"
        self.lock = threading.RLock()

    def _run(self, operation: Any) -> Any:
        with self.lock:
            connection = None
            try:
                connection = _connect(self.db_path)
                repository = ClientV2Repository(connection)
                return operation(repository)
            except ClientError as exc:
                raise ClientStoreError(exc.code, exc.message, _status_for(exc)) from exc
            except ClientStoreError:
                raise
            except Exception as exc:
                raise ClientStoreError(
                    "CLIENT_STORAGE_ERROR",
                    f"Opération client impossible: {exc}",
                    503,
                ) from exc
            finally:
                if connection is not None:
                    connection.close()

    def list_clients(
        self, *, search: str = "", include_archived: bool = True
    ) -> list[dict[str, Any]]:
        records = self._run(
            lambda repository: repository.list_clients(
                include_archived=include_archived,
                search=search,
            )
        )
        return [_record_payload(record) for record in records]

    def get(self, client_id: str) -> dict[str, Any]:
        return _record_payload(self._run(lambda repository: repository.require(client_id)))

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        def operation(repository: ClientV2Repository) -> ClientV2Record:
            record = ClientV2Record.new(
                company_name=payload["company_name"],
                address=payload.get("address", ""),
                address_line1=payload.get("address_line1", ""),
                address_line2=payload.get("address_line2", ""),
                postal_code=payload.get("postal_code", ""),
                city=payload.get("city", ""),
                country=payload.get("country", ""),
                contact_name=payload.get("contact_name", ""),
                email=payload.get("email", ""),
                phone=payload.get("phone", ""),
            )
            return repository.create(
                record,
                allow_duplicate=bool(payload.get("allow_duplicate", False)),
            )

        return _record_payload(self._run(operation))

    def update(self, client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        def operation(repository: ClientV2Repository) -> ClientV2Record:
            current = repository.require(client_id)
            updated = current.changed(
                company_name=payload.get("company_name", current.company_name),
                address=payload.get("address", current.address),
                address_line1=payload.get("address_line1", current.address_line1),
                address_line2=payload.get("address_line2", current.address_line2),
                postal_code=payload.get("postal_code", current.postal_code),
                city=payload.get("city", current.city),
                country=payload.get("country", current.country),
                contact_name=payload.get("contact_name", current.contact_name),
                email=payload.get("email", current.email),
                phone=payload.get("phone", current.phone),
            )
            return repository.update(
                updated,
                allow_duplicate=bool(payload.get("allow_duplicate", False)),
            )

        return _record_payload(self._run(operation))

    def archive(self, client_id: str) -> dict[str, Any]:
        return _record_payload(self._run(lambda repository: repository.archive(client_id)))

    def reactivate(self, client_id: str) -> dict[str, Any]:
        return _record_payload(self._run(lambda repository: repository.reactivate(client_id)))

    def set_logo(self, client_id: str, data: bytes) -> dict[str, Any]:
        if not data:
            raise ClientStoreError("CLIENT_LOGO_VIDE", "Le fichier logo est vide.", 422)
        if len(data) > MAX_LOGO_BYTES:
            raise ClientStoreError(
                "CLIENT_LOGO_TROP_VOLUMINEUX",
                "Le logo dépasse la limite de 5 Mo.",
                413,
            )
        with self.lock:
            self.logo_root.mkdir(parents=True, exist_ok=True)
            temp_path: Path | None = None
            stored: str | None = None
            try:
                fd, name = tempfile.mkstemp(
                    dir=self.logo_root,
                    prefix=".upload-",
                    suffix=".bin",
                )
                temp_path = Path(name)
                with open(fd, "wb", closefd=True) as handle:
                    handle.write(data)
                    handle.flush()
                logo_store = LogoStore(self.logo_root)
                logo_store.validate_source(temp_path)
                connection = _connect(self.db_path)
                try:
                    repository = ClientV2Repository(connection)
                    current = repository.require(client_id)
                    old_logo = current.logo
                    stored = logo_store.store(temp_path, owner_id=current.id)
                    try:
                        updated = repository.set_logo(client_id, stored)
                    except Exception:
                        logo_store.delete(stored)
                        stored = None
                        raise
                finally:
                    connection.close()
                if old_logo and old_logo != stored:
                    logo_store.delete(old_logo)
                return _record_payload(updated)
            except ClientError as exc:
                raise ClientStoreError(exc.code, exc.message, _status_for(exc)) from exc
            except ClientStoreError:
                raise
            except Exception as exc:
                raise ClientStoreError(
                    "CLIENT_LOGO_STOCKAGE_ECHEC",
                    f"Impossible de stocker le logo: {exc}",
                    503,
                ) from exc
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)

    def remove_logo(self, client_id: str) -> dict[str, Any]:
        with self.lock:
            connection = None
            try:
                connection = _connect(self.db_path)
                repository = ClientV2Repository(connection)
                current = repository.require(client_id)
                old_logo = current.logo
                updated = repository.set_logo(client_id, None)
            except ClientError as exc:
                raise ClientStoreError(exc.code, exc.message, _status_for(exc)) from exc
            finally:
                if connection is not None:
                    connection.close()
            if old_logo:
                LogoStore(self.logo_root).delete(old_logo)
            return _record_payload(updated)

    def read_logo(self, client_id: str) -> tuple[bytes, str]:
        with self.lock:
            connection = None
            try:
                connection = _connect(self.db_path)
                repository = ClientV2Repository(connection)
                record = repository.require(client_id)
            except ClientError as exc:
                raise ClientStoreError(exc.code, exc.message, _status_for(exc)) from exc
            finally:
                if connection is not None:
                    connection.close()
            if not record.logo:
                raise ClientStoreError("CLIENT_LOGO_ABSENT", "Aucun logo client.", 404)
            try:
                target = LogoStore(self.logo_root).resolve(record.logo)
            except ClientError as exc:
                raise ClientStoreError(exc.code, exc.message, _status_for(exc)) from exc
            if target is None or not target.is_file():
                raise ClientStoreError("CLIENT_LOGO_ABSENT", "Logo client introuvable.", 404)
            return target.read_bytes(), _logo_mime(record.logo)

    def snapshot(self, client_id: str) -> ClientSnapshot:
        record = self._run(lambda repository: repository.require(client_id))
        return ClientSnapshot(
            client_id=record.id,
            company_name=record.company_name,
            address=record.formatted_address,
            country=record.country,
            contact_name=record.contact_name,
            email=record.email,
            phone=record.phone,
            logo=record.logo,
            captured_at=utc_now(),
        )

    def close(self) -> None:
        # Connections are short-lived per operation.
        return None
