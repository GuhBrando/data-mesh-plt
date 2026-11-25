"""The data product repository's SQL, run on the ODPS plan 1 schema in a
throwaway Postgres (TEST_DATABASE_URL). Each test runs in a rolled-back
transaction, so the repository's own transactions become savepoints, as they
do inside a use case."""

import dataclasses
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest

from backend.domain.entities.contract_version import ContractBaseline
from backend.domain.entities.data_product import (
    ContractRef,
    ContractSummary,
    DataProduct,
    DataProductRuleError,
    InputPort,
    OutputPort,
    PortUsage,
    ProductRef,
)
from backend.infra.repositories.data_contract_repository import (
    PostgresDataContractRepository,
)
from backend.infra.repositories.data_product_repository import (
    PostgresDataProductRepository,
)
from backend.infra.repositories.domain_repository import PostgresDomainRepository
from tests.integration.odps_schema import DATABASE_URL, migrated, requires_database

pytestmark = requires_database


@pytest.fixture
async def db():
    conn = await asyncpg.connect(DATABASE_URL)
    tx = conn.transaction()
    await tx.start()
    try:
        await migrated(conn)
        yield conn
    finally:
        await tx.rollback()
        await conn.close()


@pytest.fixture
def repo(db):
    return PostgresDataProductRepository(db)


async def _domain(db, name="Risco"):
    return await db.fetchval(
        "INSERT INTO catalog.domains (name) VALUES ($1) RETURNING id", name
    )


async def _contract(db, domain_id, title="Orders", versions=("1.0.0",), status="active"):
    contract_id = await db.fetchval(
        "INSERT INTO catalog.data_contracts (title, version, domain_id, status)"
        " VALUES ($1, $2, $3, $4) RETURNING id",
        title,
        versions[-1] if versions else "1.0",
        domain_id,
        status,
    )
    for version in versions:
        await db.execute(
            "INSERT INTO catalog.contract_versions (contract_id, version, yaml_content)"
            " VALUES ($1, $2, 'y')",
            contract_id,
            version,
        )
    return contract_id


def _product(domain_id, name="Risk", **kw):
    fields = {
        "name": name,
        "description": "d",
        "domain_id": domain_id,
        "status": "active",
        "output_ports": [OutputPort("out")],
    }
    return DataProduct(**{**fields, **kw})


def _bare(ports):
    return sorted(
        (dataclasses.replace(p, id=None) for p in ports), key=lambda p: (p.name, p.version or "")
    )


async def test_add_then_get_round_trips_every_port_field(db, repo):
    domain_id = await _domain(db)
    cid = await _contract(db, domain_id)
    inputs = [
        InputPort("cad", cid, "1.0.0"),
        InputPort(
            "core",
            authoritative_definitions=({"type": "implementation", "url": "https://x"},),
        ),
    ]
    outputs = [
        OutputPort(
            "exposure",
            cid,
            "1.0.0",
            type="tables",
            description="desc",
            input_contracts=(ContractRef(cid, "1.0.0"),),
        ),
        OutputPort("alert", type="topic", deprecated=True, version="0.1"),
    ]
    saved = await repo.add(
        _product(domain_id, input_ports=inputs, output_ports=outputs)
    )
    got = await repo.get_by_id(saved.id)
    assert _bare(got.input_ports) == _bare(inputs)
    assert _bare(got.output_ports) == _bare(outputs)
    assert all(p.id is not None for p in got.input_ports + got.output_ports)
    assert (got.name, got.description, got.status) == ("Risk", "d", "active")
    assert (got.domain_id, got.domain) == (domain_id, "Risco")
    assert got.created_at is not None and got.repo_url is None


async def test_read_carries_the_contract_summary(db, repo):
    domain_id = await _domain(db)
    cid = await _contract(db, domain_id, versions=("1.0.0", "1.1.0"))
    saved = await repo.add(
        _product(domain_id, output_ports=[OutputPort("out", cid, "1.0.0"), OutputPort("free")])
    )
    by_name = {p.name: p for p in saved.output_ports}
    assert by_name["out"].contract == ContractSummary("Orders", "active", "1.1.0", "Risco")
    assert by_name["free"].contract is None


async def test_lineage_runs_through_the_same_contract_version(db, repo):
    domain_id = await _domain(db)
    cid = await _contract(db, domain_id, versions=("1.0.0", "2.0.0"))
    producer = await repo.add(
        _product(domain_id, "Producer", output_ports=[OutputPort("orders", cid, "1.0.0")])
    )
    consumer = await repo.add(
        _product(
            domain_id,
            "Consumer",
            status="draft",
            input_ports=[InputPort("orders", cid, "1.0.0")],
        )
    )
    await repo.add(
        _product(domain_id, "Other", input_ports=[InputPort("orders", cid, "2.0.0")])
    )
    consumer = await repo.get_by_id(consumer.id)
    producer = await repo.get_by_id(producer.id)
    assert consumer.input_ports[0].produced_by == (
        ProductRef(producer.id, "Producer", "active"),
    )
    assert producer.output_ports[0].consumed_by == (
        ProductRef(consumer.id, "Consumer", "draft"),
    )


async def test_a_product_is_not_its_own_counterpart(db, repo):
    domain_id = await _domain(db)
    cid = await _contract(db, domain_id)
    saved = await repo.add(
        _product(
            domain_id,
            input_ports=[InputPort("orders", cid, "1.0.0")],
            output_ports=[OutputPort("orders", cid, "1.0.0")],
        )
    )
    assert saved.input_ports[0].produced_by == ()
    assert saved.output_ports[0].consumed_by == ()


async def test_replace_keeps_port_ids_including_null_versions(db, repo):
    domain_id = await _domain(db)
    saved = await repo.add(
        _product(domain_id, input_ports=[InputPort("core")], output_ports=[OutputPort("out")])
    )
    ids = {p.name: p.id for p in saved.input_ports + saved.output_ports}
    revised = saved.revised(
        name="Risk",
        description="d",
        domain_id=domain_id,
        status="active",
        input_ports=[InputPort("core", deprecated=True)],
        output_ports=[OutputPort("out", description="now described")],
    )
    replaced = await repo.replace(revised)
    assert {p.name: p.id for p in replaced.input_ports + replaced.output_ports} == ids
    assert replaced.input_ports[0].deprecated is True
    assert replaced.output_ports[0].description == "now described"


async def test_replace_drops_ports_left_out_and_clears_the_legacy_link(db, repo):
    domain_id = await _domain(db)
    cid = await _contract(db, domain_id)
    product_id = await db.fetchval(
        "INSERT INTO catalog.data_products (name, description, domain_id, data_contracts_id)"
        " VALUES ('Legacy', 'd', $1, $2) RETURNING id",
        domain_id,
        cid,
    )
    await db.execute(
        "INSERT INTO catalog.data_product_ports (data_product_id, role, name)"
        " VALUES ($1, 'output', 'old')",
        product_id,
    )
    replaced = await repo.replace(
        _product(domain_id, "Legacy", id=product_id, output_ports=[OutputPort("orders", cid, "1.0.0")])
    )
    assert [p.name for p in replaced.output_ports] == ["orders"]
    link = await db.fetchval(
        "SELECT data_contracts_id FROM catalog.data_products WHERE id = $1", product_id
    )
    assert link is None


async def test_replace_of_a_missing_product_returns_none(db, repo):
    domain_id = await _domain(db)
    assert await repo.replace(_product(domain_id, id=uuid.uuid4())) is None


async def test_unknown_contract_version_is_a_rule_error(db, repo):
    domain_id = await _domain(db)
    cid = await _contract(db, domain_id)
    with pytest.raises(DataProductRuleError) as e:
        await repo.add(_product(domain_id, input_ports=[InputPort("cad", cid, "9.9.9")]))
    assert e.value.messages == ["Version 9.9.9 of contract Orders does not exist"]


async def test_unknown_contract_is_a_rule_error(db, repo):
    domain_id = await _domain(db)
    missing = uuid.uuid4()
    with pytest.raises(DataProductRuleError) as e:
        await repo.add(_product(domain_id, output_ports=[OutputPort("out", missing, "1.0.0")]))
    assert e.value.messages == [f"Contract {missing} does not exist"]


async def test_unknown_contract_without_version_is_a_rule_error(db, repo):
    domain_id = await _domain(db)
    missing = uuid.uuid4()
    with pytest.raises(DataProductRuleError) as e:
        await repo.add(_product(domain_id, output_ports=[OutputPort("out", missing)]))
    assert e.value.messages == [f"Contract {missing} does not exist"]


async def test_duplicate_port_key_is_a_rule_error(db, repo):
    domain_id = await _domain(db)
    with pytest.raises(DataProductRuleError) as e:
        await repo.add(_product(domain_id, output_ports=[OutputPort("x"), OutputPort("x")]))
    assert e.value.messages == [
        "Two outputs share the name x and version (none); each port needs its own"
    ]


async def test_unknown_domain_is_a_rule_error(db, repo):
    missing = uuid.uuid4()
    with pytest.raises(DataProductRuleError) as e:
        await repo.add(_product(missing))
    assert e.value.messages == [f"Domain {missing} does not exist"]


async def test_a_failed_write_leaves_nothing_and_the_transaction_usable(db, repo):
    domain_id = await _domain(db)
    with pytest.raises(DataProductRuleError):
        await repo.add(_product(domain_id, output_ports=[OutputPort("x"), OutputPort("x")]))
    assert await db.fetchval("SELECT count(*) FROM catalog.data_products") == 0


async def test_list_is_newest_first(db, repo):
    domain_id = await _domain(db)
    first = await repo.add(_product(domain_id, "First"))
    await db.execute(
        "UPDATE catalog.data_products SET updated_at = now() - interval '1 day'"
        " WHERE id = $1",
        first.id,
    )
    await repo.add(_product(domain_id, "Second"))
    assert [p.name for p in await repo.list()] == ["Second", "First"]


async def test_list_port_usage_returns_both_roles(db, repo):
    domain_id = await _domain(db)
    cid = await _contract(db, domain_id)
    producer = await repo.add(
        _product(domain_id, "Producer", output_ports=[OutputPort("orders", cid, "1.0.0")])
    )
    consumer = await repo.add(
        _product(domain_id, "Consumer", status="draft", input_ports=[InputPort("in", cid, "1.0.0")])
    )
    usage = await repo.list_port_usage([cid])
    assert usage == [
        PortUsage(producer.id, "Producer", "Risco", "active", "output", "orders", cid, "1.0.0"),
        PortUsage(consumer.id, "Consumer", "Risco", "draft", "input", "in", cid, "1.0.0"),
    ]


async def test_contract_delete_reports_the_ports_using_it(db, repo):
    domain_id = await _domain(db)
    cid = await _contract(db, domain_id)
    await repo.add(
        _product(
            domain_id,
            input_ports=[InputPort("in", cid, "1.0.0")],
            output_ports=[OutputPort("out", cid, "1.0.0")],
        )
    )
    with pytest.raises(ValueError) as e:
        await PostgresDataContractRepository(db).delete(cid)
    assert str(e.value) == (
        "Cannot delete this contract: 2 data product ports use it."
        " Remove those ports first."
    )


async def test_a_contract_without_history_can_be_used_after_its_baseline(db, repo):
    domain_id = await _domain(db)
    cid = await _contract(db, domain_id, versions=())
    contracts = PostgresDataContractRepository(db)
    at = datetime.now(tz=timezone.utc)
    await contracts.add_baseline_versions([ContractBaseline(cid, "1.0", "y", at)])
    await contracts.add_baseline_versions([ContractBaseline(cid, "1.0", "other", at)])
    saved = await repo.add(_product(domain_id, input_ports=[InputPort("in", cid, "1.0")]))
    assert saved.input_ports[0].version == "1.0"
    assert await contracts.get_version_yaml(cid, "1.0") == "y"


async def test_list_by_ids_reads_only_the_asked_contracts(db):
    domain_id = await _domain(db)
    wanted = await _contract(db, domain_id, title="Wanted")
    await _contract(db, domain_id, title="Other")
    contracts = await PostgresDataContractRepository(db).list_by_ids([wanted])
    assert [(c.id, c.title, c.domain) for c in contracts] == [(wanted, "Wanted", "Risco")]


async def test_domain_delete_mentions_products(db, repo):
    domain_id = await _domain(db, "Lonely")
    await repo.add(_product(domain_id))
    with pytest.raises(ValueError, match="data contracts or data products"):
        await PostgresDomainRepository(db).delete(domain_id)
