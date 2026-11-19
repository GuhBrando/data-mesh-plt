import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.domain.contract_evolution import ContractEvolutionError, RetiredContractError
from backend.domain.entities.data_contract import CONTRACT_VALUE_FIELDS, DataContract
from backend.use_cases.data_contract.create import CreateDataContractUseCase
from backend.use_cases.data_contract.update import UpdateDataContractUseCase
from backend.use_cases.data_contract.yaml_builder import assemble_yaml

CID, DOMAIN_ID, USER_ID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
NOW = datetime.now(tz=timezone.utc)
EARLIER = NOW - timedelta(days=1)
FIELD = {"name": "id", "type": "string", "description": "", "nullable": False,
         "primary_key": True}
WITH_AMOUNT = {"fields": [FIELD, {**FIELD, "name": "amount", "primary_key": False}],
               "quality": []}
NO_FIELDS = {"fields": [], "quality": []}
METADATA = dict(description={"purpose": "", "usage": "", "limitations": ""},
                team_members=[], support=[], servers=[])


def _contract(**kw) -> DataContract:
    defaults = dict(id=CID, title="T", version="1.0.0", owner="o", domain="d",
                    domain_id=DOMAIN_ID, tier=3, status="active",
                    models={"fields": [FIELD], "quality": []},
                    servicelevels={"properties": []}, created_at=NOW, updated_at=NOW)
    return DataContract(**{**defaults, **kw})


def _values(contract: DataContract) -> dict:
    return {name: getattr(contract, name) for name in ("domain_id", *CONTRACT_VALUE_FIELDS)}


async def _put(repo, before: DataContract, after: DataContract, **changes):
    """`before` is the locked row; the repository's update returns `after`.

    Without `changes`, the request sends every value of `after`.
    """
    repo.get_by_id_for_update.return_value = before
    repo.update.return_value = after
    return await UpdateDataContractUseCase(repo).execute(
        CID, changes or _values(after), created_by=USER_ID)


@pytest.mark.parametrize("before, after, message", [
    pytest.param(_contract(), _contract(models=WITH_AMOUNT), "property 'amount' added",
                 id="change-without-bump"),
    pytest.param(_contract(), _contract(models=NO_FIELDS, version="1.1.0"),
                 "require a MAJOR version bump", id="bump-smaller-than-the-change"),
    pytest.param(_contract(status="deprecated"),
                 _contract(status="deprecated", models=WITH_AMOUNT), "require a MINOR",
                 id="deprecated"),
    pytest.param(_contract(), _contract(status="draft", models=WITH_AMOUNT),
                 "require a MINOR", id="previous-status-decides"),
])
async def test_policy_rejection_writes_no_snapshot(contract_repo, before, after, message):
    with pytest.raises(ContractEvolutionError, match=message):
        await _put(contract_repo, before, after)
    contract_repo.add_version.assert_not_called()


@pytest.mark.parametrize("before, after", [
    pytest.param(_contract(), _contract(status="deprecated"), id="status-only"),
    pytest.param(_contract(status="draft"), _contract(status="draft", models=NO_FIELDS),
                 id="draft-changes-freely"),
    pytest.param(_contract(), _contract(status="retired"), id="any-status-can-retire"),
    pytest.param(_contract(version="1.0"), _contract(version="1.0", status="deprecated"),
                 id="unchanged-legacy-version"),
    pytest.param(_contract(), _contract(models={"fields": [
        {**FIELD, "classification": "", "unique": False, "physical_type": ""}],
        "quality": []}), id="resubmitted-form-defaults"),
])
async def test_allowed_change_in_the_same_version_writes_no_snapshot(
    contract_repo, before, after
):
    assert await _put(contract_repo, before, after) == (before, after)
    contract_repo.add_version.assert_not_called()
    contract_repo.add_baseline_version.assert_not_called()


async def test_bump_snapshots_the_old_version_then_the_new_one(contract_repo):
    before = _contract(updated_at=EARLIER)
    after = _contract(version="1.1.0", models=WITH_AMOUNT)
    await _put(contract_repo, before, after)
    contract_repo.transaction.assert_called_once()
    contract_repo.add_baseline_version.assert_called_once_with(
        CID, "1.0.0", assemble_yaml(before), EARLIER)
    contract_repo.add_version.assert_called_once_with(CID, "1.1.0", assemble_yaml(after), USER_ID)
    names = [call[0] for call in contract_repo.method_calls]
    assert names.index("add_baseline_version") < names.index("add_version")


async def test_absent_and_none_fields_keep_the_locked_values(contract_repo):
    stored = _contract(servers=[{"server": "s", "type": "local", "path": "./a"}])
    await _put(contract_repo, stored, stored, status="deprecated", owner=None, servers=[])
    assert contract_repo.update.call_args.kwargs == {
        "contract_id": CID, **_values(stored), "status": "deprecated", "servers": []}


async def test_retired_contract_rejects_every_update(contract_repo):
    retired = _contract(status="retired")
    with pytest.raises(RetiredContractError, match="retired"):
        await _put(contract_repo, retired, retired)
    contract_repo.update.assert_not_called()
    contract_repo.add_version.assert_not_called()


async def test_new_version_must_be_semver(contract_repo):
    with pytest.raises(ValueError, match="MAJOR.MINOR.PATCH"):
        await _put(contract_repo, _contract(), _contract(version="1.1"))
    contract_repo.update.assert_not_called()
    contract_repo.add_version.assert_not_called()


async def test_missing_contract_returns_none(contract_repo):
    contract_repo.get_by_id_for_update.return_value = None
    assert await UpdateDataContractUseCase(contract_repo).execute(CID, {"title": "T"}) is None
    contract_repo.update.assert_not_called()


async def test_create_writes_the_first_snapshot_without_a_baseline(contract_repo):
    created = _contract(status="draft")
    contract_repo.create.return_value = created
    await CreateDataContractUseCase(contract_repo).execute(
        title="T", version="1.0.0", owner="o", domain_id=DOMAIN_ID, tier=3,
        status="draft", models=created.models, servicelevels={"properties": []},
        **METADATA, created_by=USER_ID)
    contract_repo.add_version.assert_called_once_with(CID, "1.0.0", assemble_yaml(created), USER_ID)
    contract_repo.add_baseline_version.assert_not_called()


async def test_create_rejects_a_non_semver_version(contract_repo):
    with pytest.raises(ValueError, match="MAJOR.MINOR.PATCH"):
        await CreateDataContractUseCase(contract_repo).execute(
            title="T", version="1.0", owner="o", domain_id=DOMAIN_ID, tier=3,
            status="draft", models=NO_FIELDS, servicelevels={"properties": []}, **METADATA)
    contract_repo.create.assert_not_called()
