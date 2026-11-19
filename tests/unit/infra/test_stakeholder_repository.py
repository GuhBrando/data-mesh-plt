import uuid
from unittest.mock import AsyncMock

from backend.infra.repositories.stakeholder_repository import PostgresStakeholderRepository


async def test_contract_ids_of_returns_the_users_contracts():
    ids = [uuid.uuid4(), uuid.uuid4()]
    db = AsyncMock()
    db.fetch.return_value = [{"contract_id": i} for i in ids]
    user_id = uuid.uuid4()
    assert await PostgresStakeholderRepository(db).contract_ids_of(user_id) == set(ids)
    query, arg = db.fetch.call_args.args
    assert "WHERE user_id = $1" in query and arg == user_id
