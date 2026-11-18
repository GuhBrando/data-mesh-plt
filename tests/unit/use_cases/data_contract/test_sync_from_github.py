import uuid
from datetime import datetime, timezone
from unittest.mock import ANY, AsyncMock

import pytest
import yaml

from backend.domain.entities.data_contract import DataContract
from backend.domain.entities.domain import Domain
from backend.use_cases.data_contract.odcs import from_odcs, to_odcs
from backend.use_cases.data_contract.sync_from_github import SyncFromGitHubUseCase
from backend.use_cases.data_contract.yaml_builder import assemble_yaml
from tests.fixtures.odcs.sample_contract import sample_contract
from tests.quality_rule_builders import orders_contract

NOW = datetime.now(tz=timezone.utc)
DOMAIN_ID = uuid.uuid4()
CONTRACT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
FIELD = {"name": "id", "type": "string", "description": "", "nullable": False,
         "primary_key": True}


def _yaml(
    *,
    contract_id=None,
    domain="commerce",
    title="Orders",
    owner="alice",
    version="1.0.0",
    status="draft",
    tier=2,
    models=None,
    quality=None,
    servicelevels=None,
) -> str:
    data: dict = {
        "dataContractSpecification": "0.9.3",
        "id": str(contract_id or CONTRACT_ID),
        "info": {
            "title": title,
            "owner": owner,
            "domain": domain,
            "version": version,
            "status": status,
        },
        "x-tier": tier,
        "models": models or {},
    }
    if quality:
        data["quality"] = quality
    if servicelevels:
        data["servicelevels"] = servicelevels
    return yaml.dump(data)


def _domain(name: str = "commerce") -> Domain:
    return Domain(id=DOMAIN_ID, name=name, created_at=NOW, updated_at=NOW)


def _contract(domain: str = "commerce", status: str = "draft", version: str = "1.0.0",
              models=None) -> DataContract:
    return DataContract(
        id=CONTRACT_ID,
        title="Orders",
        version=version,
        owner="alice",
        domain=domain,
        domain_id=DOMAIN_ID,
        tier=2,
        status=status,
        models=models if models is not None else {"fields": []},
        servicelevels={"properties": []},
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def repo(contract_repo):
    contract_repo.get_by_id_for_update.return_value = None   # new contract by default
    contract_repo.get_by_id.return_value = _contract()       # the read after upsert
    contract_repo.upsert.return_value = True
    return contract_repo


@pytest.fixture
def github():
    g = AsyncMock()
    g.list_all_yaml_contents.return_value = []
    return g


@pytest.fixture
def domain_repo():
    d = AsyncMock()
    d.find_by_name.return_value = _domain()
    return d


@pytest.fixture
def use_case(repo, github, domain_repo):
    return SyncFromGitHubUseCase(repository=repo, github=github, domain_repo=domain_repo)


async def test_empty_repo_returns_zeros(use_case):
    result = await use_case.execute()
    assert result == {"created": 0, "updated": 0, "errors": []}


async def test_creates_new_contract(use_case, github, repo):
    github.list_all_yaml_contents.return_value = [("commerce/orders.yaml", _yaml())]
    repo.upsert.return_value = True
    result = await use_case.execute()
    assert result["created"] == 1
    assert result["updated"] == 0
    assert result["errors"] == []


async def test_updates_existing_contract(use_case, github, repo):
    github.list_all_yaml_contents.return_value = [("commerce/orders.yaml", _yaml())]
    repo.upsert.return_value = False
    result = await use_case.execute()
    assert result["updated"] == 1
    assert result["created"] == 0


async def test_missing_domain_name_adds_error(use_case, github):
    content = yaml.dump(
        {
            "dataContractSpecification": "0.9.3",
            "id": str(CONTRACT_ID),
            "info": {"title": "X", "owner": "o"},
        }
    )
    github.list_all_yaml_contents.return_value = [("x.yaml", content)]
    result = await use_case.execute()
    assert len(result["errors"]) == 1
    assert result["errors"][0]["path"] == "x.yaml"
    assert "no domain" in result["errors"][0]["error"]


async def test_domain_mismatch_adds_error(use_case, github, repo):
    repo.get_by_id_for_update.return_value = _contract(domain="other")
    github.list_all_yaml_contents.return_value = [
        ("commerce/orders.yaml", _yaml(domain="commerce"))
    ]
    result = await use_case.execute()
    assert len(result["errors"]) == 1
    assert "domain mismatch" in result["errors"][0]["error"]


async def test_exception_during_processing_adds_error(use_case, github):
    content = yaml.dump({"info": {"title": "X"}})  # missing 'id' key
    github.list_all_yaml_contents.return_value = [("bad.yaml", content)]
    result = await use_case.execute()
    assert result["errors"][0]["path"] == "bad.yaml"
    assert result["created"] == 0


async def test_quality_merged_into_models(use_case, github, repo):
    github.list_all_yaml_contents.return_value = [
        ("c/o.yaml", _yaml(models={"field1": {}}, quality=[{"dimension": "freshness"}]))
    ]
    await use_case.execute()
    quality = repo.upsert.call_args.kwargs["models"]["quality"]
    assert [rule["type"] for rule in quality] == ["text"]
    assert "[legacy rule: dimension=freshness" in quality[0]["description"]


async def test_resolve_domain_creates_when_not_found(use_case, github, repo, domain_repo):
    domain_repo.find_by_name.return_value = None
    domain_repo.create.return_value = _domain()
    github.list_all_yaml_contents.return_value = [("c/o.yaml", _yaml())]
    result = await use_case.execute()
    domain_repo.create.assert_called_once()
    assert result["created"] == 1


async def test_upsert_called_with_correct_fields(use_case, github, repo):
    github.list_all_yaml_contents.return_value = [
        ("c/o.yaml", _yaml(title="Invoices", owner="bob", tier=3, version="2.0.0"))
    ]
    await use_case.execute()
    kwargs = repo.upsert.call_args.kwargs
    assert kwargs["title"] == "Invoices"
    assert kwargs["owner"] == "bob"
    assert kwargs["tier"] == 3
    assert kwargs["version"] == "2.0.0"


async def test_multiple_yamls_counted_separately(use_case, github, repo):
    repo.upsert.side_effect = [True, False, True]
    github.list_all_yaml_contents.return_value = [
        ("a/a.yaml", _yaml(contract_id=uuid.uuid4())),
        ("b/b.yaml", _yaml(contract_id=uuid.uuid4())),
        ("c/c.yaml", _yaml(contract_id=uuid.uuid4())),
    ]
    result = await use_case.execute()
    assert result["created"] == 2
    assert result["updated"] == 1


def _odcs_yaml(**overrides) -> str:
    return yaml.dump({**to_odcs(sample_contract()), **overrides})


async def test_odcs_file_is_upserted_with_the_contract_values(use_case, github, repo):
    contract = sample_contract()
    github.list_all_yaml_contents.return_value = [("c/o.yaml", _odcs_yaml())]
    result = await use_case.execute()
    assert result == {"created": 1, "updated": 0, "errors": []}
    assert repo.upsert.call_args.kwargs == {
        "contract_id": contract.id,
        "title": contract.title,
        "version": contract.version,
        "owner": contract.owner,
        "domain_id": DOMAIN_ID,
        "tier": contract.tier,
        "status": contract.status,
        "models": contract.models,
        "servicelevels": contract.servicelevels,
        "description": contract.description,
        "team_members": contract.team_members,
        "support": contract.support,
        "servers": contract.servers,
    }


async def test_odcs_file_without_domain_keeps_the_error_message(use_case, github):
    doc = to_odcs(sample_contract())
    del doc["domain"]
    github.list_all_yaml_contents.return_value = [("x.yaml", yaml.dump(doc))]
    result = await use_case.execute()
    assert result["errors"] == [
        {"path": "x.yaml", "error": "YAML has no domain name; skipped"}
    ]


async def test_unsupported_odcs_key_is_reported_and_nothing_is_written(
    use_case, github, repo
):
    github.list_all_yaml_contents.return_value = [
        ("c/o.yaml", _odcs_yaml(tags=["x"]))
    ]
    result = await use_case.execute()
    assert "unsupported keys: tags" in result["errors"][0]["error"]
    repo.upsert.assert_not_called()


@pytest.mark.parametrize("content", ["", "- a\n- b\n", "just text"])
async def test_non_mapping_file_is_reported_and_the_next_file_still_syncs(
    use_case, github, repo, content
):
    github.list_all_yaml_contents.return_value = [
        ("c/empty.yaml", content),
        ("c/o.yaml", _odcs_yaml()),
    ]
    result = await use_case.execute()
    assert result["created"] == 1
    assert result["errors"] == [
        {"path": "c/empty.yaml", "error": "contract file is not a YAML mapping"}
    ]


async def test_sync_passes_metadata_to_upsert(use_case, github, repo):
    github.list_all_yaml_contents.return_value = [("c/o.yaml", _odcs_yaml(
        description={"purpose": "p"},
        team={"name": "alice", "members": [{"username": "a"}]},
        support=[{"channel": "c"}],
        servers=[{"server": "dev", "type": "local", "path": "./a", "format": "csv"}],
    ))]
    result = await use_case.execute()
    assert result["errors"] == []
    kwargs = repo.upsert.call_args.kwargs
    assert kwargs["description"] == {"purpose": "p", "usage": "", "limitations": ""}
    assert kwargs["team_members"] == [{"username": "a", "name": "", "role": ""}]
    assert kwargs["support"] == [{"channel": "c", "url": "", "tool": "", "scope": ""}]
    assert kwargs["servers"][0]["path"] == "./a"


async def test_sync_file_without_sections_clears_them(use_case, github, repo):
    existing = _contract()
    existing.team_members = [{"username": "a", "name": "", "role": ""}]
    existing.servers = [{"server": "dev", "type": "local", "path": "./a", "format": "csv"}]
    repo.get_by_id_for_update.return_value = existing
    github.list_all_yaml_contents.return_value = [("c/o.yaml", _odcs_yaml())]
    result = await use_case.execute()
    assert result["errors"] == []
    kwargs = repo.upsert.call_args.kwargs
    assert kwargs["description"] == {"purpose": "", "usage": "", "limitations": ""}
    assert (kwargs["team_members"], kwargs["support"], kwargs["servers"]) == ([], [], [])


async def test_sync_reports_a_server_with_a_secret_and_skips_the_file(use_case, github, repo):
    github.list_all_yaml_contents.return_value = [("c/o.yaml", _odcs_yaml(
        servers=[{"server": "dev", "type": "local", "path": "./a", "format": "csv",
                  "password": "not-a-real-secret"}],
    ))]
    result = await use_case.execute()
    assert result["errors"][0]["path"] == "c/o.yaml" and "password" in result["errors"][0]["error"]
    assert "not-a-real-secret" not in str(result)
    repo.upsert.assert_not_called()


async def test_sync_stores_library_rules_and_structured_sla(use_case, github, repo):
    contract = orders_contract()
    github.list_all_yaml_contents.return_value = [
        ("c/o.yaml", yaml.safe_dump(to_odcs(contract)))
    ]
    result = await use_case.execute()
    assert result["errors"] == []
    kwargs = repo.upsert.call_args.kwargs
    assert kwargs["servicelevels"] == contract.servicelevels
    stored = kwargs["models"]["quality"]
    assert sorted(rule["metric"] or "" for rule in stored) == [
        "", "duplicateValues", "invalidValues", "nullValues", "nullValues", "rowCount",
    ]


async def test_sync_reports_unsupported_rule_and_keeps_row(use_case, github, repo):
    doc = to_odcs(orders_contract())
    doc["schema"][0]["properties"][0]["quality"].append(
        {"metric": "rowCount", "mustBeBetween": [1, 2]}
    )
    github.list_all_yaml_contents.return_value = [("c/o.yaml", yaml.safe_dump(doc))]
    result = await use_case.execute()
    assert "mustBeBetween" in result["errors"][0]["error"]
    repo.upsert.assert_not_called()


def _sync(repo, github, stored, after, content):
    repo.get_by_id_for_update.return_value = stored
    if after is not None:
        repo.get_by_id.return_value = after
    repo.upsert.return_value = stored is None
    github.list_all_yaml_contents.return_value = [("c/o.yaml", content)]


async def test_new_contract_writes_the_first_snapshot(use_case, github, repo):
    _sync(repo, github, None, _contract(), _yaml())
    await use_case.execute(created_by=USER_ID)
    repo.add_version.assert_called_once_with(CONTRACT_ID, "1.0.0", ANY, USER_ID)
    repo.add_baseline_version.assert_not_called()


async def test_version_change_writes_a_snapshot(use_case, github, repo):
    _sync(repo, github, _contract(status="active"),
          _contract(status="active", version="1.0.1"),
          _yaml(version="1.0.1", status="active"))
    result = await use_case.execute()
    assert result == {"created": 0, "updated": 1, "errors": []}
    repo.add_version.assert_called_once()


async def test_unchanged_file_writes_no_snapshot(use_case, github, repo):
    _sync(repo, github, _contract(status="active"), _contract(status="active"),
          _yaml(status="active"))
    result = await use_case.execute()
    assert result["updated"] == 1
    repo.add_version.assert_not_called()


async def test_breaking_change_without_bump_is_reported_and_skipped(use_case, github, repo):
    _sync(repo, github, _contract(status="active", models={"fields": [FIELD]}),
          _contract(status="active", models={"fields": []}), _yaml(status="active"))
    result = await use_case.execute()
    errors = result["errors"]
    assert result["updated"] == 0
    assert errors[0]["path"] == "c/o.yaml"
    assert "require a MAJOR version bump" in errors[0]["error"]
    repo.add_version.assert_not_called()


async def test_file_behind_database_is_reported_and_skipped(use_case, github, repo):
    _sync(repo, github, _contract(status="active", version="1.1.0"),
          _contract(status="active", version="1.0.0"), _yaml(status="active"))
    result = await use_case.execute()
    assert "lower than the current version 1.1.0" in result["errors"][0]["error"]


async def test_retired_contract_with_unchanged_file_is_silent(use_case, github, repo):
    stored = _contract(status="retired")
    _sync(repo, github, stored, None, assemble_yaml(stored))
    result = await use_case.execute()
    assert result == {"created": 0, "updated": 0, "errors": []}
    repo.upsert.assert_not_called()


async def test_retired_contract_with_changed_file_is_reported(use_case, github, repo):
    _sync(repo, github, _contract(status="retired"), None, _yaml(status="active"))
    result = await use_case.execute()
    assert "is retired" in result["errors"][0]["error"]
    repo.upsert.assert_not_called()


async def test_invalid_version_is_reported_before_any_write(use_case, github, repo, domain_repo):
    domain_repo.find_by_name.return_value = None
    _sync(repo, github, None, None, _yaml(version="1.0"))
    result = await use_case.execute()
    assert "MAJOR.MINOR.PATCH" in result["errors"][0]["error"]
    domain_repo.create.assert_not_called()
    repo.upsert.assert_not_called()


async def test_one_rejected_file_does_not_stop_the_others(use_case, github, repo):
    github.list_all_yaml_contents.return_value = [
        ("a.yaml", _yaml(contract_id=uuid.uuid4())),
        ("b.yaml", _yaml(contract_id=uuid.uuid4(), version="bad")),
        ("c.yaml", _yaml(contract_id=uuid.uuid4())),
    ]
    result = await use_case.execute()
    assert result["created"] == 2
    assert [e["path"] for e in result["errors"]] == ["b.yaml"]


def test_retired_round_trips_through_odcs():
    assert from_odcs(to_odcs(_contract(status="retired"))).status == "retired"


async def test_long_error_is_cut_to_a_bounded_size(use_case, github):
    content = yaml.dump({"apiVersion": "v2" + "x" * 1000, "kind": "DataContract"})
    github.list_all_yaml_contents.return_value = [("x.yaml", content)]
    result = await use_case.execute()
    error = result["errors"][0]["error"]
    assert len(error) <= 501
    assert error.endswith("…")


async def test_yaml_alias_bomb_is_reported_and_skipped(use_case, github, repo):
    bomb = "\n".join(['a: &a ["x", "x"]', "b: &b [*a, *a]", "c: [*b, *b]"])
    github.list_all_yaml_contents.return_value = [("x.yaml", bomb)]
    result = await use_case.execute()
    assert "aliases" in result["errors"][0]["error"]
    repo.upsert.assert_not_called()
