"""Local company profile for WEB-08 L5.3.

The profile is stored in the existing ``company_profile`` table of
``clients.db``.  It is a singleton (id=1) and is never created implicitly.
"""

from __future__ import annotations

import re
import tempfile
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from calcelect.clients.errors import (
    ClientError,
    ClientStorageError,
    ClientValidationError,
    LogoValidationError,
)
from calcelect.clients.logos import LogoStore
from calcelect.clients.normalization import (
    clean_optional_text,
    utc_now,
    validate_email,
    validate_logo_reference,
)

from .client_v2 import MAX_LOGO_BYTES, _connect

_COMPANY_ID = 1
_SIREN_RE = re.compile(r"^\d{9}$")
_SIRET_RE = re.compile(r"^\d{14}$")
_VAT_RE = re.compile(r"^[A-Z]{2}[0-9A-Z]{2,15}$")
_COMPANY_FIELDS = (
    "legal_name",
    "trade_name",
    "address_line1",
    "address_line2",
    "postal_code",
    "city",
    "country",
    "phone",
    "email",
    "website",
    "siren",
    "siret",
    "vat_number",
    "manager_name",
    "manager_role",
    "document_footer",
)
_DB_FIELDS = (
    "legal_name",
    "trade_name",
    "address_line1",
    "address_line2",
    "postal_code",
    "city",
    "country",
    "phone",
    "email",
    "website",
    "siren",
    "siret",
    "vat_number",
    "logo",
    "manager_name",
    "manager_role",
    "document_footer",
)


class CompanyStoreError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _status_for(exc: ClientError) -> int:
    if isinstance(exc, ClientStorageError):
        return 503
    if isinstance(exc, LogoValidationError):
        return 422
    if isinstance(exc, ClientValidationError):
        return 422
    return 422


def _clean(value: object, field: str, maximum: int, *, required: bool = False) -> str:
    return (
        clean_optional_text(
            value,
            field=field,
            max_length=maximum,
            multiline=field in {"address_line1", "address_line2", "document_footer"},
        )
        if not required
        else clean_optional_text(
            value,
            field=field,
            max_length=maximum,
        )
    )


def _required(value: object, field: str, maximum: int) -> str:
    cleaned = _clean(value, field, maximum)
    if not cleaned:
        raise CompanyStoreError(
            "COMPANY_CHAMP_OBLIGATOIRE", f"Le champ {field} est obligatoire.", 422
        )
    return cleaned


def _digits(value: object, field: str, pattern: re.Pattern[str], maximum: int) -> str:
    body = _clean(value, field, maximum)
    if not body:
        return ""
    compact = re.sub(r"[\s.]", "", body)
    if not pattern.fullmatch(compact):
        raise CompanyStoreError("COMPANY_CHAMP_INVALIDE", f"Le champ {field} est invalide.", 422)
    return compact


def _website(value: object) -> str:
    body = _clean(value, "website", 300)
    if not body:
        return ""
    parsed = urlparse(body)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CompanyStoreError(
            "COMPANY_SITE_INVALIDE", "Le site internet doit être une URL http/https.", 422
        )
    return body


def _vat(value: object) -> str:
    body = _clean(value, "vat_number", 30).upper()
    if body and not _VAT_RE.fullmatch(body):
        raise CompanyStoreError(
            "COMPANY_TVA_INVALIDE", "La TVA intracommunautaire est invalide.", 422
        )
    return body


def _empty_profile() -> dict[str, Any]:
    return {
        "legal_name": "",
        "trade_name": "",
        "address_line1": "",
        "address_line2": "",
        "postal_code": "",
        "city": "",
        "country": "",
        "phone": "",
        "email": "",
        "website": "",
        "siren": "",
        "siret": "",
        "vat_number": "",
        "manager_name": "",
        "manager_role": "",
        "document_footer": "",
        "logo": None,
    }


def _row_to_payload(row: Any) -> dict[str, Any]:
    profile = _empty_profile()
    for field in _COMPANY_FIELDS:
        profile[field] = str(row[field] or "")
    profile["logo"] = row["logo"]
    profile["configured"] = bool(profile["legal_name"].strip())
    return profile


def _validate(payload: dict[str, Any], current_logo: str | None) -> dict[str, Any]:
    legal_name = _required(payload.get("legal_name"), "legal_name", 200)
    profile = {
        "legal_name": legal_name,
        "trade_name": _clean(payload.get("trade_name"), "trade_name", 200),
        "address_line1": _clean(payload.get("address_line1"), "address_line1", 200),
        "address_line2": _clean(payload.get("address_line2"), "address_line2", 200),
        "postal_code": _clean(payload.get("postal_code"), "postal_code", 20),
        "city": _clean(payload.get("city"), "city", 120),
        "country": _clean(payload.get("country"), "country", 100),
        "phone": _clean(payload.get("phone"), "phone", 60),
        "email": validate_email(payload.get("email", "")),
        "website": _website(payload.get("website")),
        "siren": _digits(payload.get("siren"), "siren", _SIREN_RE, 20),
        "siret": _digits(payload.get("siret"), "siret", _SIRET_RE, 25),
        "vat_number": _vat(payload.get("vat_number")),
        "manager_name": _clean(payload.get("manager_name"), "manager_name", 200),
        "manager_role": _clean(payload.get("manager_role"), "manager_role", 200),
        "document_footer": _clean(payload.get("document_footer"), "document_footer", 1000),
        "logo": validate_logo_reference(current_logo),
    }
    return profile


def _logo_mime(reference: str) -> str:
    suffix = Path(reference).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")


class CompanyStore:
    """Thread-safe singleton company profile."""

    def __init__(self, db_path: Path | None = None) -> None:
        from .runtime_paths import data_root

        self.db_path = Path(db_path) if db_path is not None else data_root() / "data" / "clients.db"
        self.logo_root = self.db_path.parent / "company"
        self.lock = threading.RLock()

    def _read(self, connection: Any) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM company_profile WHERE id = ?", (_COMPANY_ID,)
        ).fetchone()
        return _empty_profile() | {"configured": False} if row is None else _row_to_payload(row)

    def get(self) -> dict[str, Any]:
        with self.lock:
            connection = None
            try:
                connection = _connect(self.db_path)
                return self._read(connection)
            except ClientError as exc:
                raise CompanyStoreError(exc.code, exc.message, _status_for(exc)) from exc
            except CompanyStoreError:
                raise
            except Exception as exc:
                raise CompanyStoreError(
                    "COMPANY_STORAGE_ERROR", f"Lecture entreprise impossible: {exc}", 503
                ) from exc
            finally:
                if connection is not None:
                    connection.close()

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            connection = None
            try:
                connection = _connect(self.db_path)
                current = self._read(connection)
                profile = _validate(payload, current.get("logo"))
                now = utc_now().isoformat()
                exists = connection.execute(
                    "SELECT id FROM company_profile WHERE id = ?", (_COMPANY_ID,)
                ).fetchone()
                if exists is None:
                    connection.execute(
                        """
                        INSERT INTO company_profile (
                            id, legal_name, trade_name, address_line1, address_line2,
                            postal_code, city, country, phone, email, website, siren, siret,
                            vat_number, logo, manager_name, manager_role, document_footer,
                            created_at, updated_at
                        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (*tuple(profile[field] for field in _DB_FIELDS), now, now),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE company_profile SET
                            legal_name=?, trade_name=?, address_line1=?, address_line2=?,
                            postal_code=?, city=?, country=?, phone=?, email=?, website=?,
                            siren=?, siret=?, vat_number=?, logo=?, manager_name=?,
                            manager_role=?, document_footer=?, updated_at=?
                        WHERE id=1
                        """,
                        (*tuple(profile[field] for field in _DB_FIELDS), now),
                    )
                connection.commit()
                row = connection.execute("SELECT * FROM company_profile WHERE id = 1").fetchone()
                return _row_to_payload(row)
            except ClientError as exc:
                raise CompanyStoreError(exc.code, exc.message, _status_for(exc)) from exc
            except CompanyStoreError:
                raise
            except Exception as exc:
                raise CompanyStoreError(
                    "COMPANY_STORAGE_ERROR", f"Écriture entreprise impossible: {exc}", 503
                ) from exc
            finally:
                if connection is not None:
                    connection.close()

    def set_logo(self, data: bytes) -> dict[str, Any]:
        if not data:
            raise CompanyStoreError("COMPANY_LOGO_VIDE", "Le fichier logo est vide.", 422)
        if len(data) > MAX_LOGO_BYTES:
            raise CompanyStoreError(
                "COMPANY_LOGO_TROP_VOLUMINEUX", "Le logo dépasse la limite de 5 Mo.", 413
            )
        with self.lock:
            self.logo_root.mkdir(parents=True, exist_ok=True)
            temp_path: Path | None = None
            stored: str | None = None
            try:
                fd, name = tempfile.mkstemp(dir=self.logo_root, prefix=".upload-", suffix=".bin")
                temp_path = Path(name)
                with open(fd, "wb", closefd=True) as handle:
                    handle.write(data)
                    handle.flush()
                logo_store = LogoStore(self.logo_root)
                logo_store.validate_source(temp_path)
                connection = _connect(self.db_path)
                try:
                    current = self._read(connection)
                    old_logo = current.get("logo")
                    if not current.get("configured"):
                        raise CompanyStoreError(
                            "COMPANY_NON_CONFIGUREE",
                            "Configurez l'entreprise avant d'ajouter un logo.",
                            422,
                        )
                    stored = logo_store.store(temp_path, owner_id="company")
                    connection.execute(
                        "UPDATE company_profile SET logo = ?, updated_at = ? WHERE id = 1",
                        (stored, utc_now().isoformat()),
                    )
                    connection.commit()
                finally:
                    connection.close()
                if old_logo and old_logo != stored:
                    logo_store.delete(old_logo)
                return self.get()
            except ClientError as exc:
                raise CompanyStoreError(exc.code, exc.message, _status_for(exc)) from exc
            except CompanyStoreError:
                raise
            except Exception as exc:
                raise CompanyStoreError(
                    "COMPANY_LOGO_STOCKAGE_ECHEC", f"Stockage logo impossible: {exc}", 503
                ) from exc
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)

    def remove_logo(self) -> dict[str, Any]:
        with self.lock:
            connection = None
            try:
                connection = _connect(self.db_path)
                current = self._read(connection)
                old_logo = current.get("logo")
                connection.execute(
                    "UPDATE company_profile SET logo = NULL, updated_at = ? WHERE id = 1",
                    (utc_now().isoformat(),),
                )
                connection.commit()
            except ClientError as exc:
                raise CompanyStoreError(exc.code, exc.message, _status_for(exc)) from exc
            finally:
                if connection is not None:
                    connection.close()
            if old_logo:
                LogoStore(self.logo_root).delete(old_logo)
            return self.get()

    def read_logo(self) -> tuple[bytes, str]:
        profile = self.get()
        reference = profile.get("logo")
        if not reference:
            raise CompanyStoreError("COMPANY_LOGO_ABSENT", "Aucun logo entreprise.", 404)
        try:
            target = LogoStore(self.logo_root).resolve(reference)
        except ClientError as exc:
            raise CompanyStoreError(exc.code, exc.message, _status_for(exc)) from exc
        if target is None or not target.is_file():
            raise CompanyStoreError("COMPANY_LOGO_ABSENT", "Logo entreprise introuvable.", 404)
        return target.read_bytes(), _logo_mime(reference)
