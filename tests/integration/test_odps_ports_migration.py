"""ODPS plan 1 migration, run against a throwaway Postgres.

Set TEST_DATABASE_URL to an empty database. Every test runs in one transaction
that is rolled back. The rules the database owns (rule 3, the port key, the
output-only fields) are proven here, not only in the use cases.
"""

import asyncpg
import pytest

from tests.integration.odps_schema import (
    DATABASE_URL,
    before_plan_1,
    requires_database,
    run_plan_1,
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
    await before_plan_1(conn)
    await run_plan_1(conn)
    return conn


async def _domain(conn, name="Risco"):
    return await conn.fetchval(
        "INSERT INTO catalog.domains (name) VALUES ($1) RETURNING id", name
    )


async def _contract(conn, domain_id, version="1.0.0", status="active"):
    contract_id = await conn.fetchval(
        "INSERT INTO catalog.data_contracts (title, version, domain_id, status)"
        " VALUES ('Orders', $1, $2, $3) RETURNING id",
        version,
        domain_id,
        status,
    )
    await conn.execute(
        "INSERT INTO catalog.contract_versions (contract_id, version, yaml_content)"
        " VALUES ($1, $2, 'y')",
        contract_id,
        version,
    )
    return contract_id


async def _product(conn, domain_id):
    return await conn.fetchval(
        "INSERT INTO catalog.data_products (name, description, domain_id)"
        " VALUES ('P', 'd', $1) RETURNING id",
        domain_id,
    )


async def _port(conn, product_id, **values):
    row = {"role": "output", "name": "out", **values}
    columns = ", ".join(row)
    params = ", ".join(f"${i + 2}" for i in range(len(row)))
    return await conn.fetchval(
        f"INSERT INTO catalog.data_product_ports (data_product_id, {columns})"
        f" VALUES ($1, {params}) RETURNING id",
        product_id,
        *row.values(),
    )


async def test_existing_product_takes_its_contracts_domain_and_is_active(conn):
    await before_plan_1(conn)
    domain_id = await _domain(conn)
    contract_id = await _contract(conn, domain_id)
    product_id = await conn.fetchval(
        "INSERT INTO catalog.data_products (name, description, data_contracts_id)"
        " VALUES ('Legacy', 'd', $1) RETURNING id",
        contract_id,
    )
    await run_plan_1(conn)
    row = await conn.fetchrow(
        "SELECT domain_id, status, data_contracts_id FROM catalog.data_products"
        " WHERE id = $1",
        product_id,
    )
    assert row["domain_id"] == domain_id
    assert row["status"] == "active"
    assert row["data_contracts_id"] == contract_id


async def test_new_product_defaults_to_draft_without_a_contract(db):
    product_id = await _product(db, await _domain(db))
    row = await db.fetchrow(
        "SELECT status, data_contracts_id FROM catalog.data_products WHERE id = $1",
        product_id,
    )
    assert row["status"] == "draft"
    assert row["data_contracts_id"] is None


async def test_unknown_status_is_refused(db):
    product_id = await _product(db, await _domain(db))
    with pytest.raises(asyncpg.CheckViolationError, match="chk_dp_status"):
        await db.execute(
            "UPDATE catalog.data_products SET status = 'live' WHERE id = $1",
            product_id,
        )


async def test_product_needs_an_existing_domain(db):
    with pytest.raises(
        asyncpg.ForeignKeyViolationError, match="data_products_domain_id_fkey"
    ):
        await db.execute(
            "INSERT INTO catalog.data_products (name, description, domain_id)"
            " VALUES ('P', 'd', gen_random_uuid())"
        )


async def test_port_without_contract_keeps_a_free_version(db):
    product_id = await _product(db, await _domain(db))
    port_id = await _port(db, product_id, version="whatever")
    assert port_id is not None


async def test_port_on_a_missing_contract_version_is_refused(db):
    domain_id = await _domain(db)
    contract_id = await _contract(db, domain_id)
    product_id = await _product(db, domain_id)
    with pytest.raises(
        asyncpg.ForeignKeyViolationError, match="fk_dpp_contract_version"
    ):
        await _port(db, product_id, contract_id=contract_id, version="9.9.9")


async def test_contract_port_needs_a_version(db):
    domain_id = await _domain(db)
    contract_id = await _contract(db, domain_id)
    product_id = await _product(db, domain_id)
    with pytest.raises(asyncpg.CheckViolationError, match="chk_dpp_contract_version"):
        await _port(db, product_id, contract_id=contract_id)


@pytest.mark.parametrize(
    "field, value",
    [("type", "tables"), ("description", "d"), ("input_contracts", '[{"x": 1}]')],
)
async def test_input_port_refuses_output_only_fields(db, field, value):
    product_id = await _product(db, await _domain(db))
    with pytest.raises(asyncpg.CheckViolationError, match="chk_dpp_output_only"):
        await _port(db, product_id, role="input", **{field: value})


async def test_unknown_role_is_refused(db):
    product_id = await _product(db, await _domain(db))
    with pytest.raises(asyncpg.CheckViolationError, match="chk_dpp_role"):
        await _port(db, product_id, role="internal")


async def test_port_key_treats_missing_versions_as_equal(db):
    product_id = await _product(db, await _domain(db))
    await _port(db, product_id, role="input", name="core")
    with pytest.raises(asyncpg.UniqueViolationError, match="uq_dpp_key"):
        await _port(db, product_id, role="input", name="core")


async def test_same_name_in_two_versions_is_two_ports(db):
    domain_id = await _domain(db)
    contract_id = await _contract(db, domain_id)
    await db.execute(
        "INSERT INTO catalog.contract_versions (contract_id, version, yaml_content)"
        " VALUES ($1, '2.0.0', 'y')",
        contract_id,
    )
    product_id = await _product(db, domain_id)
    await _port(db, product_id, contract_id=contract_id, version="1.0.0")
    await _port(db, product_id, contract_id=contract_id, version="2.0.0")
    count = await db.fetchval("SELECT count(*) FROM catalog.data_product_ports")
    assert count == 2


async def test_deleting_a_used_contract_fails_and_keeps_history(db):
    domain_id = await _domain(db)
    contract_id = await _contract(db, domain_id)
    product_id = await _product(db, domain_id)
    await _port(db, product_id, contract_id=contract_id, version="1.0.0")
    with pytest.raises(
        asyncpg.ForeignKeyViolationError, match="fk_dpp_contract_version"
    ):
        async with db.transaction():
            await db.execute(
                "DELETE FROM catalog.data_contracts WHERE id = $1", contract_id
            )
    assert await db.fetchval("SELECT count(*) FROM catalog.contract_versions") == 1
    assert await db.fetchval("SELECT count(*) FROM catalog.data_contracts") == 1


async def test_deleting_a_product_deletes_its_ports(db):
    product_id = await _product(db, await _domain(db))
    await _port(db, product_id)
    await db.execute("DELETE FROM catalog.data_products WHERE id = $1", product_id)
    assert await db.fetchval("SELECT count(*) FROM catalog.data_product_ports") == 0


async def test_platform_data_port_tables_and_types_are_gone(db):
    names = await db.fetch(
        "SELECT to_regclass(n) AS t FROM unnest(ARRAY["
        "'platform.data_ports', 'platform.data_ports_type',"
        " 'platform.product_port_binding']) AS n"
    )
    assert [r["t"] for r in names] == [None, None, None]
    types = await db.fetchval(
        "SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace"
        " WHERE n.nspname = 'platform'"
        " AND t.typname IN ('port_role_type', 'binding_status')"
    )
    assert types == 0


async def test_migration_stops_when_platform_data_ports_hold_rows(conn):
    await before_plan_1(conn)
    await conn.execute(
        "INSERT INTO platform.data_ports_type (type, connection_ref, schema_ref)"
        " VALUES ('t', 'c', 's')"
    )
    with pytest.raises(asyncpg.RaiseError, match="hold rows"):
        await run_plan_1(conn)
