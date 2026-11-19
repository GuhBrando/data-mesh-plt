import uuid
from datetime import datetime, timezone

import pytest

from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.create import CreateDataContractUseCase
from backend.use_cases.data_contract.update import UpdateDataContractUseCase

NOW = datetime.now(tz=timezone.utc)
DOMAIN_ID = uuid.uuid4()
METADATA = dict(
    description={"purpose": "p", "usage": "", "limitations": ""},
    team_members=[{"username": "a", "name": "", "role": ""}],
    support=[{"channel": "c", "url": "", "tool": "", "scope": ""}],
    servers=[{"server": "s", "type": "local", "path": "./a", "format": "csv"}],
)
VALUES = dict(version="1.0.0", owner="alice", domain_id=DOMAIN_ID, tier=2, status="draft",
              models={"fields": []}, servicelevels={}, **METADATA)


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


@pytest.fixture
def repo(contract_repo):
    """Holds a draft, so an update reaches the write."""
    contract_repo.get_by_id_for_update.return_value = make_contract()
    return contract_repo


async def test_create_passes_the_values_to_the_repository(repo):
    repo.create.return_value = make_contract(title="Orders")
    result = await CreateDataContractUseCase(repo).execute(title="Orders", **VALUES)
    assert result.title == "Orders"
    assert repo.create.call_args.kwargs == {"title": "Orders", **VALUES}


async def test_update_passes_the_values_to_the_repository(repo):
    cid = uuid.uuid4()
    repo.update.return_value = make_contract(title="Updated")
    result = await UpdateDataContractUseCase(repo).execute(cid, {"title": "Updated", **VALUES})
    assert result.current.title == "Updated"
    assert repo.update.call_args.kwargs == {"contract_id": cid, "title": "Updated", **VALUES}


@pytest.mark.parametrize("execute", [
    lambda repo: CreateDataContractUseCase(repo).execute(title="", **VALUES),
    lambda repo: UpdateDataContractUseCase(repo).execute(uuid.uuid4(), {"title": ""}),
], ids=["create", "update"])
async def test_empty_title_is_rejected(repo, execute):
    with pytest.raises(ValueError, match="title"):
        await execute(repo)
    repo.create.assert_not_called()
    repo.update.assert_not_called()
