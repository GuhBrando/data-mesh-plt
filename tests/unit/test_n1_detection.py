from unittest.mock import AsyncMock

import pytest

from backend.use_cases.data_product.list import ListDataProductsUseCase


@pytest.mark.n1
async def test_list_data_products_makes_single_db_call(n1_guard):
    repo = AsyncMock()
    repo.list.return_value = []

    guard = n1_guard(repo)
    use_case = ListDataProductsUseCase(repository=repo)
    result = await use_case.execute()

    assert result == []
    guard.assert_max_calls("list", max_calls=1)


@pytest.mark.n1
async def test_n1_guard_catches_repeated_calls(n1_guard):
    """Self-test: verify the guard correctly detects repeated calls."""
    repo = AsyncMock()
    guard = n1_guard(repo)

    for _ in range(3):
        await repo.get()

    with pytest.raises(AssertionError, match="N\\+1 detected"):
        guard.assert_max_calls("get", max_calls=1)


# ── ODPS plan 1: a write or read costs the same whatever the number of ports ──

import uuid  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

from backend.domain.entities.data_product import (  # noqa: E402
    DataProduct,
    InputPort,
    ManagementPort,
    OutputPort,
)
from backend.infra.repositories.data_contract_repository import (  # noqa: E402
    PostgresDataContractRepository,
)
from backend.infra.repositories.data_product_repository import (  # noqa: E402
    PostgresDataProductRepository,
)


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _db():
    db = MagicMock()
    db.execute, db.fetch, db.fetchrow, db.fetchval = (AsyncMock() for _ in range(4))
    db.fetchval.return_value = uuid.uuid4()
    db.fetchrow.return_value = None
    db.fetch.return_value = []
    db.transaction = MagicMock(return_value=_Transaction())
    return db


def _with_ports(n: int) -> DataProduct:
    return DataProduct(
        id=uuid.uuid4(),
        name="P",
        domain_id=uuid.uuid4(),
        input_ports=[InputPort(f"in{i}") for i in range(n)],
        output_ports=[OutputPort(f"out{i}") for i in range(n)],
        management_ports=[ManagementPort(f"m{i}", "control") for i in range(n)],
    )


def _calls(db) -> tuple[int, int, int, int]:
    return (
        db.execute.await_count,
        db.fetch.await_count,
        db.fetchrow.await_count,
        db.fetchval.await_count,
    )


@pytest.mark.n1
@pytest.mark.parametrize("method", ["add", "replace"])
async def test_product_write_cost_does_not_grow_with_ports(method):
    counts = []
    for n in (1, 5):
        db = _db()
        await getattr(PostgresDataProductRepository(db), method)(_with_ports(n))
        counts.append(_calls(db))
    # One row write, one ports statement, one management ports statement, one read-back.
    assert counts[0] == counts[1] == (2, 0, 1, 1)


@pytest.mark.n1
@pytest.mark.parametrize(
    "method, args, guarded",
    [
        ("get_by_id", (uuid.uuid4(),), "fetchrow"),
        ("list", (), "fetch"),
        ("list_port_usage", ([uuid.uuid4(), uuid.uuid4(), uuid.uuid4()],), "fetch"),
    ],
)
async def test_product_reads_are_single_queries(n1_guard, method, args, guarded):
    db = _db()
    await getattr(PostgresDataProductRepository(db), method)(*args)
    n1_guard(db).assert_max_calls(guarded, max_calls=1)
    assert sum(_calls(db)) == 1


@pytest.mark.n1
async def test_contracts_by_ids_is_one_query(n1_guard):
    db = _db()
    await PostgresDataContractRepository(db).list_by_ids([uuid.uuid4() for _ in range(5)])
    assert sum(_calls(db)) == 1


@pytest.mark.n1
async def test_baselines_are_one_statement():
    from datetime import datetime, timezone

    from backend.domain.entities.contract_version import ContractBaseline

    db = _db()
    at = datetime.now(tz=timezone.utc)
    await PostgresDataContractRepository(db).add_baseline_versions(
        [ContractBaseline(uuid.uuid4(), "1.0.0", "y", at) for _ in range(5)]
    )
    assert sum(_calls(db)) == 1


@pytest.mark.n1
async def test_member_domain_ids_is_one_query():
    from backend.interface.permissions import member_domain_ids

    db = _db()
    await member_domain_ids(uuid.uuid4(), db)
    assert sum(_calls(db)) == 1


@pytest.mark.n1
async def test_stakeholder_list_is_one_query():
    from backend.infra.repositories.stakeholder_repository import (
        PostgresStakeholderRepository,
    )

    db = _db()
    await PostgresStakeholderRepository(db).list_for_contract(uuid.uuid4())
    assert sum(_calls(db)) == 1
