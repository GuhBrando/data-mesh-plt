"""The contract history migration, run against a throwaway Postgres.

Set TEST_DATABASE_URL to an empty database. The fixture creates the catalog
schema itself, so it fails on a database that already has one, which keeps the
test away from real data. Every test runs in one transaction that is rolled back.
"""

import os
from pathlib import Path

import asyncpg
import pytest

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not set")

SQL_FILE = (
    Path(__file__).parents[2]
    / "database/migrations/20261101000005_contract_versions.sql"
)
# The roles and default privileges the earlier migrations leave behind: every new
# catalog table reaches admin and app_user with UPDATE and DELETE.
DDL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'admin') THEN
        CREATE ROLE admin;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user;
    END IF;
END $$;
CREATE SCHEMA catalog;
ALTER DEFAULT PRIVILEGES IN SCHEMA catalog GRANT ALL ON TABLES TO admin, app_user;
CREATE TABLE catalog.data_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL DEFAULT 'draft',
    CONSTRAINT chk_dc_status
        CHECK (status IN ('draft', 'in_review', 'active', 'deprecated'))
);
"""


@pytest.fixture
async def db():
    conn = await asyncpg.connect(DATABASE_URL)
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute(DDL)
        await conn.execute(SQL_FILE.read_text(encoding="utf-8"))
        yield conn
    finally:
        await tx.rollback()
        await conn.close()


async def _contract_with_history(conn) -> object:
    contract_id = await conn.fetchval(
        "INSERT INTO catalog.data_contracts (status) VALUES ('retired') RETURNING id"
    )
    await conn.execute(
        "INSERT INTO catalog.contract_versions (contract_id, version, yaml_content)"
        " VALUES ($1, '1.0.0', 'a'), ($1, '1.1.0', 'b')",
        contract_id,
    )
    return contract_id


@pytest.mark.parametrize("statement, operation", [
    ("UPDATE catalog.contract_versions SET yaml_content = 'x'", "UPDATE"),
    ("DELETE FROM catalog.contract_versions", "DELETE"),
    ("TRUNCATE catalog.contract_versions", "TRUNCATE"),
])
async def test_history_rows_cannot_change(db, statement, operation):
    await _contract_with_history(db)
    with pytest.raises(asyncpg.RaiseError, match=rf"immutable \({operation}\)"):
        await db.execute(statement)


async def test_deleting_the_contract_cascades_to_its_history(db):
    contract_id = await _contract_with_history(db)
    await db.execute("DELETE FROM catalog.data_contracts WHERE id = $1", contract_id)
    assert await db.fetchval("SELECT count(*) FROM catalog.contract_versions") == 0


async def test_a_delete_from_another_trigger_is_rejected(db):
    # pg_trigger_depth() > 1 would let this through: only the cascade may delete.
    await _contract_with_history(db)
    await db.execute("""
        CREATE TABLE catalog.wiper (id INT);
        CREATE FUNCTION catalog.wipe() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN DELETE FROM catalog.contract_versions; RETURN NEW; END $$;
        CREATE TRIGGER wipe AFTER INSERT ON catalog.wiper
            FOR EACH ROW EXECUTE FUNCTION catalog.wipe();
    """)
    with pytest.raises(asyncpg.RaiseError, match=r"immutable \(DELETE\)"):
        await db.execute("INSERT INTO catalog.wiper VALUES (1)")


async def test_application_roles_lose_the_write_privileges(db):
    rows = await db.fetch("""
        SELECT r.role, p.privilege,
               has_table_privilege(r.role, 'catalog.contract_versions', p.privilege)
                   AS granted
        FROM unnest(ARRAY['admin', 'app_user']) AS r(role),
             unnest(ARRAY['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']) AS p(privilege)
    """)
    granted = {(r["role"], r["privilege"]) for r in rows if r["granted"]}
    # admin keeps DELETE for the cascade it runs as the owner on azure.
    assert granted == {("admin", "INSERT"), ("admin", "DELETE"), ("app_user", "INSERT")}
