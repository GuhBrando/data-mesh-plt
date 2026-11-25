"""ODPS plan 2 migration, run against a throwaway Postgres (TEST_DATABASE_URL).

Every test runs in one transaction that is rolled back.
"""

import json

import asyncpg
import pytest

from tests.integration.odps_schema import (
    DATABASE_URL,
    before_plan_1,
    migrated,
    requires_database,
    run_plan_1,
    run_plan_2,
)

pytestmark = requires_database


@pytest.fixture
async def conn():
    conn = await asyncpg.connect(DATABASE_URL)
    tx = conn.transaction()
    await tx.start()
    try:
        yield conn
    finally:
        await tx.rollback()
        await conn.close()


@pytest.fixture
async def db(conn):
    await migrated(conn)
    return conn


async def _domain(conn):
    return await conn.fetchval(
        "INSERT INTO catalog.domains (name) VALUES ('Risco') RETURNING id"
    )


async def _plan_1_product(conn, description="Old text"):
    """A product as plan 1 leaves it: own domain, no contract link."""
    return await conn.fetchval(
        "INSERT INTO catalog.data_products (name, description, domain_id)"
        " VALUES ('P', $1, $2) RETURNING id",
        description,
        await _domain(conn),
    )


async def _product(db):
    return await db.fetchval(
        "INSERT INTO catalog.data_products (name, domain_id) VALUES ('P', $1)"
        " RETURNING id",
        await _domain(db),
    )


async def test_text_description_becomes_purpose(conn):
    await before_plan_1(conn)
    await run_plan_1(conn)
    old = await _plan_1_product(conn, "Old text")
    empty = await conn.fetchval(
        "INSERT INTO catalog.data_products (name, description, domain_id)"
        " SELECT 'E', '', domain_id FROM catalog.data_products WHERE id = $1"
        " RETURNING id",
        old,
    )
    await run_plan_2(conn)
    rows = {
        r["id"]: json.loads(r["description"])
        for r in await conn.fetch("SELECT id, description FROM catalog.data_products")
    }
    assert rows[old] == {"purpose": "Old text", "usage": "", "limitations": ""}
    assert rows[empty] == {"purpose": "", "usage": "", "limitations": ""}


async def test_new_sections_default_to_empty(db):
    product_id = await _product(db)
    row = await db.fetchrow(
        "SELECT version, type, tenant, description, tags, synonyms, context, team,"
        " support, custom_properties, authoritative_definitions"
        " FROM catalog.data_products WHERE id = $1",
        product_id,
    )
    assert (row["version"], row["type"], row["tenant"]) == (None, None, None)
    assert json.loads(row["description"]) == {"purpose": "", "usage": "", "limitations": ""}
    for column in ("tags", "synonyms", "support", "custom_properties", "authoritative_definitions"):
        assert json.loads(row[column]) == []
    assert (json.loads(row["context"]), json.loads(row["team"])) == ({}, {})


async def test_migration_stops_while_a_legacy_link_remains(conn):
    await before_plan_1(conn)
    domain_id = await _domain(conn)
    contract_id = await conn.fetchval(
        "INSERT INTO catalog.data_contracts (title, domain_id) VALUES ('C', $1) RETURNING id",
        domain_id,
    )
    await conn.execute(
        "INSERT INTO catalog.data_products (name, description, data_contracts_id)"
        " VALUES ('Legacy', 'd', $1)",
        contract_id,
    )
    await run_plan_1(conn)
    with pytest.raises(asyncpg.RaiseError, match="run the ODPS plan 1 backfill"):
        async with conn.transaction():
            await run_plan_2(conn)
    link = await conn.fetchval("SELECT data_contracts_id FROM catalog.data_products")
    assert link == contract_id


async def test_data_contracts_id_is_gone(db):
    columns = await db.fetch(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = 'catalog' AND table_name = 'data_products'"
    )
    assert "data_contracts_id" not in {c["column_name"] for c in columns}


async def test_control_tables_are_gone(db):
    tables = await db.fetchval(
        "SELECT count(*) FROM unnest(ARRAY['platform.control_ports',"
        " 'platform.control_port_types']) AS t WHERE to_regclass(t) IS NOT NULL"
    )
    assert tables == 0


async def test_migration_stops_when_control_tables_hold_rows(conn):
    await before_plan_1(conn)
    await run_plan_1(conn)
    await conn.execute(
        "INSERT INTO platform.control_port_types (name, action_url) VALUES ('t', 'u')"
    )
    with pytest.raises(asyncpg.RaiseError, match="control-port tables hold rows"):
        await run_plan_2(conn)


@pytest.mark.parametrize(
    "field, value",
    [("synonyms", '[{"synonym": "x"}]'), ("context", '{"instructions": "x"}'), ("sbom", '[{"url": "x"}]')],
)
async def test_input_port_refuses_synonyms_context_and_sbom(db, field, value):
    product_id = await _product(db)
    with pytest.raises(asyncpg.CheckViolationError, match="chk_dpp_output_only"):
        await db.execute(
            f"INSERT INTO catalog.data_product_ports (data_product_id, role, name, {field})"
            " VALUES ($1, 'input', 'in', $2::jsonb)",
            product_id,
            value,
        )


async def test_ports_take_tags_and_custom_properties(db):
    product_id = await _product(db)
    for role in ("input", "output"):
        await db.execute(
            "INSERT INTO catalog.data_product_ports"
            " (data_product_id, role, name, tags, custom_properties)"
            " VALUES ($1, $2, 'p', '[\"a\"]', '[{\"property\": \"k\", \"value\": 1}]')",
            product_id,
            role,
        )
    assert await db.fetchval("SELECT count(*) FROM catalog.data_product_ports") == 2


async def test_management_port_type_is_rest_or_topic(db):
    product_id = await _product(db)
    kind = await db.fetchval(
        "INSERT INTO catalog.data_product_management_ports (data_product_id, name, content)"
        " VALUES ($1, 'm', 'observability') RETURNING type",
        product_id,
    )
    assert kind == "rest"
    with pytest.raises(asyncpg.CheckViolationError, match="chk_dmp_type"):
        await db.execute(
            "INSERT INTO catalog.data_product_management_ports"
            " (data_product_id, name, content, type) VALUES ($1, 'g', 'control', 'grpc')",
            product_id,
        )


async def test_management_port_names_are_unique_per_product(db):
    product_id = await _product(db)
    insert = (
        "INSERT INTO catalog.data_product_management_ports (data_product_id, name, content)"
        " VALUES ($1, 'm', 'control')"
    )
    await db.execute(insert, product_id)
    with pytest.raises(asyncpg.UniqueViolationError, match="uq_dmp_name"):
        await db.execute(insert, product_id)


async def test_management_port_needs_a_content(db):
    product_id = await _product(db)
    with pytest.raises(asyncpg.NotNullViolationError):
        await db.execute(
            "INSERT INTO catalog.data_product_management_ports (data_product_id, name)"
            " VALUES ($1, 'm')",
            product_id,
        )


async def test_deleting_a_product_deletes_its_management_ports(db):
    product_id = await _product(db)
    await db.execute(
        "INSERT INTO catalog.data_product_management_ports (data_product_id, name, content)"
        " VALUES ($1, 'm', 'control')",
        product_id,
    )
    await db.execute("DELETE FROM catalog.data_products WHERE id = $1", product_id)
    count = await db.fetchval("SELECT count(*) FROM catalog.data_product_management_ports")
    assert count == 0
