import uuid
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.domain.entities.data_product import (
    DataProduct,
    DataProductRuleError,
    InputPort,
    OutputPort,
)
from backend.infra.repositories.data_product_repository import (
    PostgresDataProductRepository,
)

DOMAIN = uuid.uuid4()


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _db() -> MagicMock:
    db = MagicMock()
    db.execute, db.fetch, db.fetchrow, db.fetchval = (AsyncMock() for _ in range(4))
    db.transaction = MagicMock(return_value=_Transaction())
    return db


def _violation(cls, constraint):
    error = cls("violation")
    error.constraint_name = constraint
    return error


def _product(**kw):
    return DataProduct(
        name="P", description="d", domain_id=DOMAIN, output_ports=[OutputPort("out")], **kw
    )


async def test_output_only_violation_is_a_rule_error():
    db = _db()
    db.execute.side_effect = _violation(
        asyncpg.CheckViolationError, "chk_dpp_output_only"
    )
    with pytest.raises(DataProductRuleError) as e:
        await PostgresDataProductRepository(db).add(_product())
    assert e.value.messages == [
        "Only outputs can have a type, a description or input contracts"
    ]


async def test_status_violation_is_a_rule_error():
    db = _db()
    db.fetchval.side_effect = _violation(asyncpg.CheckViolationError, "chk_dp_status")
    with pytest.raises(DataProductRuleError, match="Status must be one of"):
        await PostgresDataProductRepository(db).add(_product())


async def test_duplicate_inputs_are_named_in_the_message():
    db = _db()
    db.execute.side_effect = asyncpg.CardinalityViolationError("twice")
    product = _product(input_ports=[InputPort("a", version="1"), InputPort("a", version="1")])
    with pytest.raises(DataProductRuleError) as e:
        await PostgresDataProductRepository(db).add(product)
    assert e.value.messages == [
        "Two inputs share the name a and version 1; each port needs its own"
    ]


async def test_an_unmapped_violation_is_raised_as_is():
    db = _db()
    error = _violation(asyncpg.UniqueViolationError, "some_other_key")
    db.execute.side_effect = error
    with pytest.raises(asyncpg.UniqueViolationError) as e:
        await PostgresDataProductRepository(db).add(_product())
    assert e.value is error


async def test_list_port_usage_skips_an_empty_list():
    db = _db()
    assert await PostgresDataProductRepository(db).list_port_usage([]) == []
    db.fetch.assert_not_awaited()


async def test_replace_writes_ports_only_when_the_product_exists():
    db = _db()
    db.fetchval.return_value = None
    product = _product(id=uuid.uuid4())
    assert await PostgresDataProductRepository(db).replace(product) is None
    db.execute.assert_not_awaited()
    db.fetchrow.assert_not_awaited()


async def test_replace_clears_the_legacy_contract_link():
    db = _db()
    db.fetchval.return_value = uuid.uuid4()
    db.fetchrow.return_value = None
    await PostgresDataProductRepository(db).replace(_product(id=uuid.uuid4()))
    assert "data_contracts_id = NULL" in db.fetchval.call_args.args[0]
