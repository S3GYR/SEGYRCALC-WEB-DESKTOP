"""WEB-08 L5.1 — client referential v2.

This module owns the WEB-08 migration and the v2 SQLite representation of the
existing client domain. It deliberately stays in the WEB-08 backend: the
historical V1.4/V1.5 client package is imported for validation helpers and logo
storage, but is not modified.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from calcelect.clients.errors import (
    ClientNotFoundError,
    ClientStorageError,
    ClientValidationError,
    DuplicateClientError,
)
from calcelect.clients.normalization import (
    clean_company_name,
    clean_optional_text,
    ensure_utc,
    normalized_company_name,
    utc_now,
    validate_email,
    validate_logo_reference,
    validate_timestamps,
)

SCHEMA_VERSION = 2
MAX_LOGO_BYTES = 5 * 1024 * 1024
MAX_ADDRESS_LINE = 200
MAX_POSTAL_CODE = 20
MAX_CITY = 120
MAX_COUNTRY = 100
MAX_PHONE = 60
MAX_CONTACT_NAME = 200
MAX_LEGACY_ADDRESS = 500

SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY NOT NULL,
    company_name TEXT NOT NULL CHECK (length(trim(company_name)) > 0),
    normalized_company_name TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    address_line1 TEXT NOT NULL DEFAULT '',
    address_line2 TEXT NOT NULL DEFAULT '',
    postal_code TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    logo TEXT,
    is_archived INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_clients_normalized_name
    ON clients(normalized_company_name);
CREATE INDEX IF NOT EXISTS idx_clients_archived
    ON clients(is_archived);
CREATE INDEX IF NOT EXISTS idx_clients_company_name
    ON clients(company_name COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY NOT NULL,
    client_id TEXT NOT NULL,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    role_title TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    mobile TEXT NOT NULL DEFAULT '',
    normalized_name TEXT NOT NULL,
    is_archived INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_contacts_client ON contacts(client_id);
CREATE INDEX IF NOT EXISTS idx_contacts_archived ON contacts(is_archived);
CREATE INDEX IF NOT EXISTS idx_contacts_normalized_name ON contacts(normalized_name);
CREATE TABLE IF NOT EXISTS company_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    legal_name TEXT NOT NULL DEFAULT '',
    trade_name TEXT NOT NULL DEFAULT '',
    address_line1 TEXT NOT NULL DEFAULT '',
    address_line2 TEXT NOT NULL DEFAULT '',
    postal_code TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    siren TEXT NOT NULL DEFAULT '',
    siret TEXT NOT NULL DEFAULT '',
    vat_number TEXT NOT NULL DEFAULT '',
    logo TEXT,
    manager_name TEXT NOT NULL DEFAULT '',
    manager_role TEXT NOT NULL DEFAULT '',
    document_footer TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY NOT NULL,
    applied_at TEXT NOT NULL
);
"""

_MIGRATION_ALTERS = (
    "ALTER TABLE clients ADD COLUMN address_line1 TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE clients ADD COLUMN address_line2 TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE clients ADD COLUMN postal_code TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE clients ADD COLUMN city TEXT NOT NULL DEFAULT ''",
)

_MIGRATION_TABLES = """
CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY NOT NULL,
    client_id TEXT NOT NULL,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    role_title TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    mobile TEXT NOT NULL DEFAULT '',
    normalized_name TEXT NOT NULL,
    is_archived INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_contacts_client ON contacts(client_id);
CREATE INDEX IF NOT EXISTS idx_contacts_archived ON contacts(is_archived);
CREATE INDEX IF NOT EXISTS idx_contacts_normalized_name ON contacts(normalized_name);
CREATE TABLE IF NOT EXISTS company_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    legal_name TEXT NOT NULL DEFAULT '',
    trade_name TEXT NOT NULL DEFAULT '',
    address_line1 TEXT NOT NULL DEFAULT '',
    address_line2 TEXT NOT NULL DEFAULT '',
    postal_code TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    siren TEXT NOT NULL DEFAULT '',
    siret TEXT NOT NULL DEFAULT '',
    vat_number TEXT NOT NULL DEFAULT '',
    logo TEXT,
    manager_name TEXT NOT NULL DEFAULT '',
    manager_role TEXT NOT NULL DEFAULT '',
    document_footer TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class ClientV2Record:
    id: str
    company_name: str
    normalized_company_name: str
    address: str
    address_line1: str
    address_line2: str
    postal_code: str
    city: str
    country: str
    contact_name: str
    email: str
    phone: str
    logo: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        try:
            parsed = UUID(self.id)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ClientValidationError(
                "L'identifiant client doit être un UUID.",
                code="CLIENT_ID_INVALIDE",
                field="id",
            ) from exc
        if str(parsed) != self.id:
            raise ClientValidationError(
                "L'identifiant client doit être un UUID canonique minuscule.",
                code="CLIENT_ID_INVALIDE",
                field="id",
            )
        company = clean_company_name(self.company_name)
        object.__setattr__(self, "company_name", company)
        object.__setattr__(self, "normalized_company_name", normalized_company_name(company))
        object.__setattr__(
            self,
            "address",
            clean_optional_text(
                self.address, field="address", max_length=MAX_LEGACY_ADDRESS, multiline=True
            ),
        )
        object.__setattr__(
            self,
            "address_line1",
            clean_optional_text(
                self.address_line1,
                field="address_line1",
                max_length=MAX_ADDRESS_LINE,
                multiline=True,
            ),
        )
        object.__setattr__(
            self,
            "address_line2",
            clean_optional_text(
                self.address_line2,
                field="address_line2",
                max_length=MAX_ADDRESS_LINE,
                multiline=True,
            ),
        )
        object.__setattr__(
            self,
            "postal_code",
            clean_optional_text(self.postal_code, field="postal_code", max_length=MAX_POSTAL_CODE),
        )
        object.__setattr__(
            self, "city", clean_optional_text(self.city, field="city", max_length=MAX_CITY)
        )
        object.__setattr__(
            self,
            "country",
            clean_optional_text(self.country, field="country", max_length=MAX_COUNTRY),
        )
        object.__setattr__(
            self,
            "contact_name",
            clean_optional_text(
                self.contact_name, field="contact_name", max_length=MAX_CONTACT_NAME
            ),
        )
        object.__setattr__(self, "email", validate_email(self.email))
        object.__setattr__(
            self, "phone", clean_optional_text(self.phone, field="phone", max_length=MAX_PHONE)
        )
        object.__setattr__(self, "logo", validate_logo_reference(self.logo))
        if not isinstance(self.is_archived, bool):
            raise ClientValidationError(
                "is_archived doit être un booléen.",
                code="CLIENT_ARCHIVE_INVALIDE",
                field="is_archived",
            )
        created, updated = validate_timestamps(self.created_at, self.updated_at)
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "updated_at", updated)

    @property
    def client_id(self) -> str:
        return self.id

    @property
    def formatted_address(self) -> str:
        parts = [
            self.address_line1,
            self.address_line2,
            " ".join(item for item in (self.postal_code, self.city) if item),
            self.country,
        ]
        structured = [part for part in parts if part]
        return (
            "\n".join(structured)
            if any((self.address_line1, self.address_line2, self.postal_code, self.city))
            else self.address
        )

    @property
    def display_name(self) -> str:
        return self.company_name

    @classmethod
    def new(
        cls,
        *,
        company_name: str,
        address: str = "",
        address_line1: str = "",
        address_line2: str = "",
        postal_code: str = "",
        city: str = "",
        country: str = "",
        contact_name: str = "",
        email: str = "",
        phone: str = "",
        logo: str | None = None,
        client_id: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> ClientV2Record:
        now = utc_now()
        created = ensure_utc(created_at, field="created_at") if created_at else now
        updated = ensure_utc(updated_at, field="updated_at") if updated_at else created
        return cls(
            id=client_id or str(uuid4()),
            company_name=company_name,
            normalized_company_name="",
            address=address,
            address_line1=address_line1,
            address_line2=address_line2,
            postal_code=postal_code,
            city=city,
            country=country,
            contact_name=contact_name,
            email=email,
            phone=phone,
            logo=logo,
            is_archived=False,
            created_at=created,
            updated_at=updated,
        )

    def changed(self, **changes: Any) -> ClientV2Record:
        change = dict(changes)
        change.setdefault("updated_at", utc_now())
        return replace(self, **change)


def _row_to_record(row: sqlite3.Row) -> ClientV2Record:
    try:
        created = datetime.fromisoformat(str(row["created_at"]))
        updated = datetime.fromisoformat(str(row["updated_at"]))
    except ValueError as exc:
        raise ClientStorageError(
            "Date client invalide dans la base.",
            code="CLIENT_DB_DATE_INVALIDE",
        ) from exc
    return ClientV2Record(
        id=str(row["id"]),
        company_name=str(row["company_name"]),
        normalized_company_name=str(row["normalized_company_name"]),
        address=str(row["address"] or ""),
        address_line1=str(row["address_line1"] or ""),
        address_line2=str(row["address_line2"] or ""),
        postal_code=str(row["postal_code"] or ""),
        city=str(row["city"] or ""),
        country=str(row["country"] or ""),
        contact_name=str(row["contact_name"] or ""),
        email=str(row["email"] or ""),
        phone=str(row["phone"] or ""),
        logo=row["logo"],
        is_archived=bool(row["is_archived"]),
        created_at=created,
        updated_at=updated,
    )


def _backup_v1(connection: sqlite3.Connection, db_path: Path) -> Path:
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_dir / f"clients-v1-{stamp}.db"
    destination = sqlite3.connect(str(backup))
    try:
        connection.backup(destination)
    finally:
        destination.close()
    digest = hashlib.sha256(backup.read_bytes()).hexdigest().upper()
    Path(str(backup) + ".sha256").write_text(f"{digest}  {backup.name}\n", encoding="utf-8")
    Path(str(backup) + ".json").write_text(
        f'{{"source":"{db_path.as_posix()}","source_schema_version":1,"backup_sha256":"{digest}"}}\n',
        encoding="utf-8",
    )
    return backup


def initialize(connection: sqlite3.Connection, db_path: Path) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    has_clients = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='clients'"
    ).fetchone()
    has_version = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()

    if not has_clients:
        connection.executescript(SCHEMA_V2)
        connection.execute("DELETE FROM schema_version")
        connection.execute(
            "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, utc_now().isoformat()),
        )
        connection.commit()
        return

    if not has_version:
        version = 1
    else:
        row = connection.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        version = int(row["version"]) if row else 1
    if version > SCHEMA_VERSION:
        raise ClientStorageError(
            "La base clients utilise un schéma plus récent que cette application.",
            code="CLIENT_DB_SCHEMA_INCOMPATIBLE",
        )
    if version == SCHEMA_VERSION:
        for table in ("contacts", "company_profile"):
            found = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if found is None:
                raise ClientStorageError(
                    "Le schéma clients v2 est incomplet.",
                    code="CLIENT_DB_SCHEMA_INCOMPLETE",
                )
        return

    _backup_v1(connection, db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _MIGRATION_ALTERS:
            connection.execute(statement)
        for statement in _MIGRATION_TABLES.split(";"):
            if statement.strip():
                connection.execute(statement)
        if not has_version:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_version "
                "(version INTEGER PRIMARY KEY NOT NULL, applied_at TEXT NOT NULL)"
            )
        connection.execute("DELETE FROM schema_version")
        connection.execute(
            "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, utc_now().isoformat()),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise ClientStorageError(
            "La migration clients v2 a échoué au contrôle d'intégrité.",
            code="CLIENT_DB_MIGRATION_INTEGRITY",
        )


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), timeout=5.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    initialize(connection, db_path)
    return connection


class ClientV2Repository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_clients(
        self,
        *,
        include_archived: bool = True,
        search: str = "",
    ) -> tuple[ClientV2Record, ...]:
        clauses: list[str] = []
        params: list[object] = []
        if not include_archived:
            clauses.append("is_archived = 0")
        if search.strip():
            needle = f"%{search.strip()}%"
            clauses.append(
                "(company_name LIKE ? OR address LIKE ? OR address_line1 LIKE ? "
                "OR address_line2 LIKE ? OR postal_code LIKE ? OR city LIKE ? "
                "OR contact_name LIKE ? OR email LIKE ? OR phone LIKE ?)"
            )
            params.extend([needle] * 9)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.connection.execute(
            f"SELECT * FROM clients{where} ORDER BY company_name COLLATE NOCASE, id",
            params,
        ).fetchall()
        return tuple(_row_to_record(row) for row in rows)

    def get(self, client_id: str) -> ClientV2Record | None:
        row = self.connection.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        return _row_to_record(row) if row is not None else None

    def require(self, client_id: str) -> ClientV2Record:
        record = self.get(client_id)
        if record is None:
            raise ClientNotFoundError(
                "La fiche client demandée n'existe pas.",
                code="CLIENT_NOT_FOUND",
                field="id",
            )
        return record

    def _duplicate(
        self, record: ClientV2Record, *, exclude_id: str | None = None
    ) -> ClientV2Record | None:
        sql = "SELECT * FROM clients WHERE normalized_company_name = ?"
        params: list[object] = [record.normalized_company_name]
        if exclude_id is not None:
            sql += " AND id <> ?"
            params.append(exclude_id)
        row = self.connection.execute(sql, params).fetchone()
        return _row_to_record(row) if row is not None else None

    def create(self, record: ClientV2Record, *, allow_duplicate: bool = False) -> ClientV2Record:
        duplicate = self._duplicate(record)
        if duplicate is not None and not allow_duplicate:
            raise DuplicateClientError(duplicate.id, duplicate.company_name)
        self.connection.execute(
            """
            INSERT INTO clients (
                id, company_name, normalized_company_name, address,
                address_line1, address_line2, postal_code, city, country,
                contact_name, email, phone, logo, is_archived, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._params(record),
        )
        return record

    def update(self, record: ClientV2Record, *, allow_duplicate: bool = False) -> ClientV2Record:
        self.require(record.id)
        duplicate = self._duplicate(record, exclude_id=record.id)
        if duplicate is not None and not allow_duplicate:
            raise DuplicateClientError(duplicate.id, duplicate.company_name)
        self.connection.execute(
            """
            UPDATE clients SET
                company_name = ?, normalized_company_name = ?, address = ?,
                address_line1 = ?, address_line2 = ?, postal_code = ?, city = ?,
                country = ?, contact_name = ?, email = ?, phone = ?, logo = ?,
                is_archived = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                record.company_name,
                record.normalized_company_name,
                record.address,
                record.address_line1,
                record.address_line2,
                record.postal_code,
                record.city,
                record.country,
                record.contact_name,
                record.email,
                record.phone,
                record.logo,
                1 if record.is_archived else 0,
                record.updated_at.isoformat(),
                record.id,
            ),
        )
        return record

    def set_logo(self, client_id: str, logo: str | None) -> ClientV2Record:
        current = self.require(client_id)
        updated = current.changed(logo=logo)
        return self.update(updated)

    def archive(self, client_id: str) -> ClientV2Record:
        current = self.require(client_id)
        return self.update(current.changed(is_archived=True))

    def reactivate(self, client_id: str) -> ClientV2Record:
        current = self.require(client_id)
        return self.update(current.changed(is_archived=False))

    def _params(self, record: ClientV2Record) -> tuple[object, ...]:
        return (
            record.id,
            record.company_name,
            record.normalized_company_name,
            record.address,
            record.address_line1,
            record.address_line2,
            record.postal_code,
            record.city,
            record.country,
            record.contact_name,
            record.email,
            record.phone,
            record.logo,
            1 if record.is_archived else 0,
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
        )


__all__ = [
    "MAX_LOGO_BYTES",
    "SCHEMA_VERSION",
    "ClientV2Record",
    "ClientV2Repository",
    "_connect",
]
