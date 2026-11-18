import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.domain.contract_evolution import ContractEvolutionError, RetiredContractError
from backend.domain.entities.data_contract import DataContract
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


async def _put(repo, before: DataContract, after: DataContract) -> DataContract | None:
    """`before` is the locked row; the repository's update returns `after`."""
    repo.get_by_id_for_update.return_value = before
    repo.update.return_value = after
    return await UpdateDataContractUseCase(repo).execute(
        contract_id=CID, title=after.title, version=after.version, owner=after.owner,
        domain_id=DOMAIN_ID, tier=after.tier, status=after.status, models=after.models,
        servicelevels=after.servicelevels, **METADATA, created_by=USER_ID)


async def test_status_only_update_keeps_working_without_a_snapshot(contract_repo):
    after = _contract(status="deprecated")
    assert await _put(contract_repo, _contract(), after) is after
    contract_repo.add_version.assert_not_called()
    contract_repo.add_baseline_version.assert_not_called()


async def test_content_change_without_bump_on_active_is_rejected(contract_repo):
    with pytest.raises(ContractEvolutionError, match="property 'amount' added"):
        await _put(contract_repo, _contract(), _contract(models=WITH_AMOUNT))
    contract_repo.add_version.assert_not_called()


async def test_bump_smaller_than_the_change_is_rejected(contract_repo):
    with pytest.raises(ContractEvolutionError, match="require a MAJOR version bump"):
        await _put(contract_repo, _contract(), _contract(models=NO_FIELDS, version="1.1.0"))
    contract_repo.add_version.assert_not_called()


async def test_deprecated_contract_is_governed(contract_repo):
    with pytest.raises(ContractEvolutionError):
        await _put(contract_repo, _contract(status="deprecated"),
                   _contract(status="deprecated", models=WITH_AMOUNT))
    contract_repo.add_version.assert_not_called()


async def test_draft_changes_freely(contract_repo):
    after = _contract(status="draft", models=NO_FIELDS)
    assert await _put(contract_repo, _contract(status="draft"), after) is after


async def test_previous_status_decides_when_rules_apply(contract_repo):
    with pytest.raises(ContractEvolutionError):
        await _put(contract_repo, _contract(), _contract(status="draft", models=WITH_AMOUNT))
    contract_repo.add_version.assert_not_called()


async def test_bump_writes_the_snapshot_inside_the_transaction(contract_repo):
    after = _contract(version="1.1.0", models=WITH_AMOUNT)
    await _put(contract_repo, _contract(), after)
    contract_repo.transaction.assert_called_once()
    contract_repo.add_version.assert_called_once_with(CID, "1.1.0", assemble_yaml(after), USER_ID)


async def test_first_bump_without_history_captures_the_old_version_first(contract_repo):
    before = _contract(updated_at=EARLIER)
    await _put(contract_repo, before, _contract(version="1.1.0", models=WITH_AMOUNT))
    contract_repo.add_baseline_version.assert_called_once_with(
        CID, "1.0.0", assemble_yaml(before), EARLIER)
    names = [call[0] for call in contract_repo.method_calls]
    assert names.index("add_baseline_version") < names.index("add_version")


async def test_retired_contract_rejects_every_update(contract_repo):
    retired = _contract(status="retired")
    with pytest.raises(RetiredContractError, match="retired"):
        await _put(contract_repo, retired, retired)
    contract_repo.update.assert_not_called()
    contract_repo.add_version.assert_not_called()


async def test_any_status_can_become_retired(contract_repo):
    after = _contract(status="retired")
    assert await _put(contract_repo, _contract(), after) is after
    contract_repo.add_version.assert_not_called()


async def test_new_version_must_be_semver(contract_repo):
    with pytest.raises(ValueError, match="MAJOR.MINOR.PATCH"):
        await _put(contract_repo, _contract(), _contract(version="1.1"))
    contract_repo.update.assert_not_called()
    contract_repo.add_version.assert_not_called()


async def test_unchanged_legacy_version_passes(contract_repo):
    after = _contract(version="1.0", status="deprecated")
    assert await _put(contract_repo, _contract(version="1.0"), after) is after


async def test_resubmitted_form_defaults_are_not_a_change(contract_repo):
    after = _contract(models={"fields": [{**FIELD, "classification": "", "unique": False,
                                          "physical_type": ""}], "quality": []})
    assert await _put(contract_repo, _contract(), after) is after


async def test_missing_contract_returns_none(contract_repo):
    contract_repo.get_by_id_for_update.return_value = None
    result = await UpdateDataContractUseCase(contract_repo).execute(
        contract_id=CID, title="T", version="1.0.0", owner="o", domain_id=DOMAIN_ID,
        tier=3, status="active", models=NO_FIELDS, servicelevels={"properties": []},
        **METADATA)
    assert result is None
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
