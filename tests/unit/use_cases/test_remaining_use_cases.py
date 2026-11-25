"""
Tests for use cases that were missing coverage:
data_contract (get, delete, list), data_product get/delete, user CRUD.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from backend.domain.entities.data_contract import DataContract
from backend.domain.entities.user import User
from backend.domain.value_objects.email import Email
from backend.use_cases.data_contract.delete import DeleteDataContractUseCase
from backend.use_cases.data_contract.get import GetDataContractUseCase
from backend.use_cases.data_contract.list import ListDataContractsUseCase
from backend.use_cases.data_product.delete import DeleteDataProductUseCase
from backend.use_cases.data_product.get import GetDataProductUseCase
from backend.use_cases.user.create import CreateUserUseCase
from backend.use_cases.user.delete import DeleteUserUseCase
from backend.use_cases.user.get import GetUserUseCase
from backend.use_cases.user.list import ListUsersUseCase
from backend.use_cases.user.update import UpdateUserUseCase

NOW = datetime.now(tz=timezone.utc)


def _contract(**kw):
    return DataContract(
        id=kw.get("id", uuid.uuid4()),
        title="Orders", version="1.0.0", owner="alice", domain="commerce",
        tier=2, status="draft", models={"fields": []},
        servicelevels={"freshness": "24h", "availability": "99%", "retention": "365d", "latency": "1h"},
        created_at=NOW, updated_at=NOW,
    )


def _user():
    return User(id=uuid.uuid4(), name="Alice", email=Email("alice@example.com"))


# ── Data Contract: get ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_data_contract_returns_contract():
    repo = AsyncMock()
    contract = _contract()
    repo.get_by_id.return_value = contract
    result = await GetDataContractUseCase(repo).execute(contract.id)
    assert result is contract
    repo.get_by_id.assert_called_once_with(contract.id)


@pytest.mark.asyncio
async def test_get_data_contract_returns_none_when_missing():
    repo = AsyncMock()
    repo.get_by_id.return_value = None
    result = await GetDataContractUseCase(repo).execute(uuid.uuid4())
    assert result is None


# ── Data Contract: delete ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_data_contract_returns_true():
    repo = AsyncMock()
    repo.delete.return_value = True
    result = await DeleteDataContractUseCase(repo).execute(uuid.uuid4())
    assert result is True


@pytest.mark.asyncio
async def test_delete_data_contract_returns_false_when_not_found():
    repo = AsyncMock()
    repo.delete.return_value = False
    result = await DeleteDataContractUseCase(repo).execute(uuid.uuid4())
    assert result is False


# ── Data Contract: list ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_data_contracts_returns_all():
    repo = AsyncMock()
    contracts = [_contract(), _contract()]
    repo.list.return_value = contracts
    result = await ListDataContractsUseCase(repo).execute()
    assert result == contracts


@pytest.mark.asyncio
async def test_list_data_contracts_returns_empty():
    repo = AsyncMock()
    repo.list.return_value = []
    result = await ListDataContractsUseCase(repo).execute()
    assert result == []


# ── Data Product: get ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_data_product_returns_product():
    from backend.domain.entities.data_product import DataProduct
    repo = AsyncMock()
    from backend.domain.entities.data_product import OutputPort
    product = DataProduct(id=uuid.uuid4(), name="Px", description="D",
                          domain_id=uuid.uuid4(), output_ports=[OutputPort("out")],
                          created_at=NOW, updated_at=NOW)
    repo.get_by_id.return_value = product
    result = await GetDataProductUseCase(repo).execute(product.id)
    assert result is product


@pytest.mark.asyncio
async def test_get_data_product_returns_none():
    repo = AsyncMock()
    repo.get_by_id.return_value = None
    result = await GetDataProductUseCase(repo).execute(uuid.uuid4())
    assert result is None


# ── Data Product: delete ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_data_product_returns_true():
    repo = AsyncMock()
    repo.delete.return_value = True
    result = await DeleteDataProductUseCase(repo).execute(uuid.uuid4())
    assert result is True


@pytest.mark.asyncio
async def test_delete_data_product_returns_false():
    repo = AsyncMock()
    repo.delete.return_value = False
    result = await DeleteDataProductUseCase(repo).execute(uuid.uuid4())
    assert result is False


# ── User: create ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user_hashes_password():
    import bcrypt
    repo = AsyncMock()
    repo.create.return_value = _user()
    await CreateUserUseCase(repo).execute(
        name="Bob", email="bob@example.com", password="Str0ng!Pass"
    )
    _, kwargs = repo.create.call_args
    assert bcrypt.checkpw(b"Str0ng!Pass", kwargs["password_hash"].encode())


@pytest.mark.asyncio
async def test_create_user_raises_on_invalid_email():
    repo = AsyncMock()
    with pytest.raises(ValueError):
        await CreateUserUseCase(repo).execute(
            name="Bob", email="not-an-email", password="Str0ng!Pass"
        )


# ── User: get ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_user_returns_user():
    repo = AsyncMock()
    user = _user()
    repo.get_by_id.return_value = user
    result = await GetUserUseCase(repo).execute(user.id)
    assert result is user


@pytest.mark.asyncio
async def test_get_user_returns_none():
    repo = AsyncMock()
    repo.get_by_id.return_value = None
    result = await GetUserUseCase(repo).execute(uuid.uuid4())
    assert result is None


# ── User: delete ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_user_returns_true():
    repo = AsyncMock()
    repo.delete.return_value = True
    result = await DeleteUserUseCase(repo).execute(uuid.uuid4())
    assert result is True


@pytest.mark.asyncio
async def test_delete_user_returns_false():
    repo = AsyncMock()
    repo.delete.return_value = False
    result = await DeleteUserUseCase(repo).execute(uuid.uuid4())
    assert result is False


# ── User: list ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_users_returns_all():
    repo = AsyncMock()
    users = [_user(), _user()]
    repo.list.return_value = users
    result = await ListUsersUseCase(repo).execute()
    assert result == users


@pytest.mark.asyncio
async def test_list_users_returns_empty():
    repo = AsyncMock()
    repo.list.return_value = []
    result = await ListUsersUseCase(repo).execute()
    assert result == []


# ── User: update ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_user_calls_repo():
    repo = AsyncMock()
    user = _user()
    repo.update.return_value = user
    result = await UpdateUserUseCase(repo).execute(
        user_id=user.id, name="Bob", email="bob@example.com"
    )
    repo.update.assert_called_once()
    assert result is user


@pytest.mark.asyncio
async def test_update_user_raises_on_invalid_email():
    repo = AsyncMock()
    with pytest.raises(ValueError):
        await UpdateUserUseCase(repo).execute(
            user_id=uuid.uuid4(), name="Bob", email="bad-email"
        )


@pytest.mark.asyncio
async def test_update_user_returns_none_when_missing():
    repo = AsyncMock()
    repo.update.return_value = None
    result = await UpdateUserUseCase(repo).execute(
        user_id=uuid.uuid4(), name=None, email=None
    )
    assert result is None
