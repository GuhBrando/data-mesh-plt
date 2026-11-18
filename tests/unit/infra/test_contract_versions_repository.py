import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.domain.contract_evolution import ContractVersionConflictError
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


async def test_add_baseline_version_keeps_an_existing_row():
    db, at = _db(), datetime.now(tz=timezone.utc)
    await PostgresDataContractRepository(db).add_baseline_version(CONTRACT_ID, "1.0.0", "y", at)
    sql, *params = db.execute.call_args.args
    assert "ON CONFLICT (contract_id, version) DO NOTHING" in sql
    assert params == [CONTRACT_ID, "1.0.0", "y", at]


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


async def test_get_version_yaml_is_none_for_an_unknown_version():
    db = _db()
    db.fetchval.return_value = None
    assert await PostgresDataContractRepository(db).get_version_yaml(CONTRACT_ID, "9.9.9") is None


def test_transaction_comes_from_the_connection():
    db = _db()
    assert PostgresDataContractRepository(db).transaction() is db.transaction.return_value
