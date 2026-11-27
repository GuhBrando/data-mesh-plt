"""The stakeholder repository's SQL, run in a throwaway Postgres
(TEST_DATABASE_URL) inside a rolled-back transaction."""

import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from backend.infra.repositories.stakeholder_repository import (
    PostgresStakeholderRepository,
)
from tests.integration.odps_schema import DATABASE_URL, migrated, requires_database

pytestmark = requires_database

# The tables this repository reads, as migrations 20260326000001 (iam.users),
# 20260420000001 (password_hash) and 20260428000001 (role, stakeholders) leave
# them. `migrated` builds only the ODPS catalog.
_ACCESS_TABLES = """
CREATE SCHEMA iam;
CREATE TABLE iam.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'DATA_CONSUMER'
        CHECK (role IN ('PLATFORM_ADMIN', 'DATA_OWNER', 'DATA_STEWARD',
                        'DATA_CONSUMER'))
);
CREATE TABLE catalog.contract_stakeholders (
    contract_id UUID NOT NULL REFERENCES catalog.data_contracts(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES iam.users(id) ON DELETE CASCADE,
    assigned_by UUID REFERENCES iam.users(id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (contract_id, user_id)
);
"""


@pytest.fixture
async def db():
    conn = await asyncpg.connect(DATABASE_URL)
    tx = conn.transaction()
    await tx.start()
    try:
        await migrated(conn)
        await conn.execute(_ACCESS_TABLES)
        yield conn
    finally:
        await tx.rollback()
        await conn.close()


async def _user(db, name: str, role: str = "DATA_CONSUMER") -> uuid.UUID:
    return await db.fetchval(
        "INSERT INTO iam.users (name, email, password_hash, role)"
        " VALUES ($1, $2, '', $3) RETURNING id",
        name,
        f"{name}@example.com",
        role,
    )


async def _contract(db) -> uuid.UUID:
    domain_id = await db.fetchval(
        "INSERT INTO catalog.domains (name) VALUES ('Risco') RETURNING id"
    )
    return await db.fetchval(
        "INSERT INTO catalog.data_contracts (title, version, domain_id, status)"
        " VALUES ('Credito', '1.0.0', $1, 'draft') RETURNING id",
        domain_id,
    )


async def test_list_for_contract_names_who_and_by_whom_in_order(db):
    contract_id = await _contract(db)
    steward = await _user(db, "joao", "DATA_STEWARD")
    ana = await _user(db, "ana")
    bia = await _user(db, "bia", "DATA_OWNER")
    earlier = datetime.now(tz=timezone.utc) - timedelta(days=2)
    await db.execute(
        "INSERT INTO catalog.contract_stakeholders"
        " (contract_id, user_id, assigned_by, assigned_at) VALUES"
        " ($1, $2, $3, now()), ($1, $4, NULL, $5)",
        contract_id,
        ana,
        steward,
        bia,
        earlier,
    )

    rows = await PostgresStakeholderRepository(db).list_for_contract(contract_id)

    assert [(r.username, r.role, r.assigned_by_username) for r in rows] == [
        ("bia", "DATA_OWNER", ""),
        ("ana", "DATA_CONSUMER", "joao"),
    ]
    assert rows[1].user_id == ana


async def test_list_for_contract_without_stakeholders_is_empty(db):
    contract_id = await _contract(db)
    assert await PostgresStakeholderRepository(db).list_for_contract(contract_id) == []
