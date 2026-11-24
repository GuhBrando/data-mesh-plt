import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.domain.contract_evolution import ContractVersionConflictError
from backend.domain.entities.contract_version import ContractBaseline
from backend.infra.repositories.data_contract_repository import (
    PostgresDataContractRepository,
)

CONTRACT_ID = uuid.uuid4()


def _db() -> MagicMock:
    db = MagicMock()
    db.execute, db.fetch, db.fetchrow, db.fetchval = (AsyncMock() for _ in range(4))
    return db


async def test_add_version_maps_unique_violation_to_conflict():
    db = _db()
    db.execute.side_effect = asyncpg.UniqueViolationError("duplicate key")
    with pytest.raises(ContractVersionConflictError, match="1.1.0"):
        await PostgresDataContractRepository(db).add_version(CONTRACT_ID, "1.1.0", "y", None)


async def test_add_version_inserts_the_snapshot():
    db, user = _db(), uuid.uuid4()
    await PostgresDataContractRepository(db).add_version(CONTRACT_ID, "1.1.0", "y", user)
    sql, *params = db.execute.call_args.args
    assert "INSERT INTO catalog.contract_versions" in sql
    assert params == [CONTRACT_ID, "1.1.0", "y", user]


async def test_add_baseline_versions_writes_all_in_one_statement():
    db, at = _db(), datetime.now(tz=timezone.utc)
    other = uuid.uuid4()
    await PostgresDataContractRepository(db).add_baseline_versions([
        ContractBaseline(CONTRACT_ID, "1.0.0", "y", at),
        ContractBaseline(other, "2.0.0", "z", at),
    ])
    db.execute.assert_awaited_once()
    sql, *params = db.execute.call_args.args
    assert "unnest" in sql
    assert "ON CONFLICT (contract_id, version) DO NOTHING" in sql
    assert params == [[CONTRACT_ID, other], ["1.0.0", "2.0.0"], ["y", "z"], [at, at]]


async def test_add_baseline_versions_skips_an_empty_list():
    db = _db()
    await PostgresDataContractRepository(db).add_baseline_versions([])
    db.execute.assert_not_awaited()


async def test_list_by_ids_reads_all_in_one_query():
    db = _db()
    db.fetch.return_value = []
    ids = [CONTRACT_ID, uuid.uuid4()]
    assert await PostgresDataContractRepository(db).list_by_ids(ids) == []
    sql, param = db.fetch.call_args.args
    assert "ANY($1::uuid[])" in sql
    assert param == ids


async def test_list_by_ids_skips_an_empty_list():
    db = _db()
    assert await PostgresDataContractRepository(db).list_by_ids([]) == []
    db.fetch.assert_not_awaited()


async def test_get_by_id_for_update_locks_only_the_contract_row():
    db = _db()
    db.fetchrow.return_value = None
    assert await PostgresDataContractRepository(db).get_by_id_for_update(CONTRACT_ID) is None
    assert "FOR UPDATE OF dc" in db.fetchrow.call_args.args[0]


async def test_list_versions_is_newest_first_and_skips_the_yaml():
    db, at = _db(), datetime.now(tz=timezone.utc)
    db.fetch.return_value = [
        {"contract_id": CONTRACT_ID, "version": "1.0.0", "created_by": None, "created_at": at}
    ]
    [row] = await PostgresDataContractRepository(db).list_versions(CONTRACT_ID)
    sql = db.fetch.call_args.args[0]
    assert "ORDER BY created_at DESC, version DESC" in sql
    assert "yaml_content" not in sql
    assert (row.contract_id, row.version, row.created_by, row.created_at) == (
        CONTRACT_ID, "1.0.0", None, at,
    )


async def test_get_version_yaml_reads_one_version_of_one_contract():
    db = _db()
    db.fetchval.return_value = "y"
    assert await PostgresDataContractRepository(db).get_version_yaml(CONTRACT_ID, "1.0.0") == "y"
    sql, *params = db.fetchval.call_args.args
    assert "WHERE contract_id = $1 AND version = $2" in sql and params == [CONTRACT_ID, "1.0.0"]


def test_transaction_comes_from_the_connection():
    db = _db()
    assert PostgresDataContractRepository(db).transaction() is db.transaction.return_value
