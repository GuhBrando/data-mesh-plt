import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.create import CreateDataContractUseCase
from backend.use_cases.data_contract.update import UpdateDataContractUseCase

NOW = datetime.now(tz=timezone.utc)


DOMAIN_ID = uuid.uuid4()


def make_contract(**kwargs) -> DataContract:
    defaults = dict(
        id=uuid.uuid4(),
        title="T",
        version="1.0.0",
        owner="o",
        domain="d",
        domain_id=DOMAIN_ID,
        tier=3,
        status="draft",
        models={"fields": []},
        servicelevels={"freshness": "", "availability": "", "retention": "", "latency": ""},
        created_at=NOW,
        updated_at=NOW,
    )
    return DataContract(**{**defaults, **kwargs})


@pytest.mark.asyncio
async def test_create_calls_repository():
    repo = AsyncMock()
    repo.create.return_value = make_contract(title="Orders")
    use_case = CreateDataContractUseCase(repo)

    result = await use_case.execute(
        title="Orders", version="1.0.0", owner="alice", domain_id=DOMAIN_ID,
        tier=2, status="draft", models={"fields": []},
        servicelevels={"freshness": "24h", "availability": "", "retention": "", "latency": ""},
        **METADATA,
    )

    repo.create.assert_called_once()
    assert result.title == "Orders"


@pytest.mark.asyncio
async def test_create_raises_on_empty_title():
    repo = AsyncMock()
    use_case = CreateDataContractUseCase(repo)

    with pytest.raises(ValueError, match="title"):
        await use_case.execute(
            title="", version="1.0.0", owner="alice", domain_id=DOMAIN_ID,
            tier=2, status="draft", models={"fields": []},
            servicelevels={"freshness": "", "availability": "", "retention": "", "latency": ""},
            **METADATA,
        )


@pytest.mark.asyncio
async def test_update_calls_repository():
    repo = AsyncMock()
    cid = uuid.uuid4()
    repo.update.return_value = make_contract(title="Updated")
    use_case = UpdateDataContractUseCase(repo)

    result = await use_case.execute(
        contract_id=cid,
        title="Updated", version="1.0.0", owner="bob", domain_id=DOMAIN_ID,
        tier=1, status="in_review", models={"fields": []},
        servicelevels={"freshness": "1h", "availability": "99.9%", "retention": "365d", "latency": "30m"},
        **METADATA,
    )

    repo.update.assert_called_once()
    assert result.title == "Updated"


@pytest.mark.asyncio
async def test_update_raises_on_empty_title():
    repo = AsyncMock()
    use_case = UpdateDataContractUseCase(repo)
    with pytest.raises(ValueError, match="title"):
        await use_case.execute(
            contract_id=uuid.uuid4(),
            title="", version="1.0.0", owner="alice", domain_id=DOMAIN_ID,
            tier=2, status="draft", models={"fields": []},
            servicelevels={"freshness": "", "availability": "", "retention": "", "latency": ""},
            **METADATA,
        )


@pytest.mark.asyncio
async def test_create_passes_title_to_repo():
    repo = AsyncMock()
    repo.create.return_value = make_contract(title="Inventory")
    await CreateDataContractUseCase(repo).execute(
        title="Inventory", version="1.0.0", owner="alice", domain_id=DOMAIN_ID,
        tier=3, status="draft", models={"fields": []},
        servicelevels={"freshness": "", "availability": "", "retention": "", "latency": ""},
        **METADATA,
    )
    assert repo.create.call_args.kwargs["title"] == "Inventory"


@pytest.mark.asyncio
async def test_update_passes_title_to_repo():
    repo = AsyncMock()
    repo.update.return_value = make_contract(title="NewName")
    await UpdateDataContractUseCase(repo).execute(
        contract_id=uuid.uuid4(),
        title="NewName", version="1.0.0", owner="bob", domain_id=DOMAIN_ID,
        tier=2, status="draft", models={"fields": []},
        servicelevels={"freshness": "", "availability": "", "retention": "", "latency": ""},
        **METADATA,
    )
    assert repo.update.call_args.kwargs["title"] == "NewName"


METADATA = dict(
    description={"purpose": "p", "usage": "", "limitations": ""},
    team_members=[{"username": "a", "name": "", "role": ""}],
    support=[{"channel": "c", "url": "", "tool": "", "scope": ""}],
    servers=[{"server": "s", "type": "local", "path": "./a", "format": "csv"}],
)

@pytest.mark.asyncio
@pytest.mark.parametrize("use_case_cls, method, extra", [
    (CreateDataContractUseCase, "create", {}),
    (UpdateDataContractUseCase, "update", {"contract_id": uuid.uuid4()}),
])
async def test_use_case_passes_metadata_to_repo(use_case_cls, method, extra):
    repo = AsyncMock()
    getattr(repo, method).return_value = make_contract()
    await use_case_cls(repo).execute(**extra, title="T", version="1.0.0", owner="o", domain_id=DOMAIN_ID,
                                     tier=3, status="draft", models={"fields": []}, servicelevels={}, **METADATA)
    assert {k: getattr(repo, method).call_args.kwargs[k] for k in METADATA} == METADATA
