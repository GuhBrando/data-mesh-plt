"""
Router integration tests using FastAPI's TestClient with dependency overrides.
Covers data_contract and users router endpoints plus main.py custom_openapi.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.domain.entities.contract_stakeholder import ContractStakeholder
from backend.domain.entities.contract_version import ContractVersion
from backend.domain.entities.data_contract import DataContract
from backend.domain.entities.user import User
from backend.domain.value_objects.email import Email
from backend.domain.value_objects.user_role import UserRole
from backend.infra.postgres import get_db_connection
from backend.interface.dependencies import (
    get_assign_role_use_case,
    get_assign_stakeholder_use_case,
    get_create_data_contract_use_case,
    get_create_user_use_case,
    get_data_contract_repository,
    get_delete_data_contract_use_case,
    get_delete_user_use_case,
    get_domain_repository,
    get_get_data_contract_use_case,
    get_get_user_use_case,
    get_get_contract_version_yaml_use_case,
    get_github_client,
    get_list_contract_versions_use_case,
    get_list_data_contracts_use_case,
    get_list_users_use_case,
    get_remove_stakeholder_use_case,
    get_stakeholder_repository,
    get_update_data_contract_use_case,
    get_update_user_use_case,
    get_user_repository,
)
from backend.interface.security import get_current_user
from backend.domain.contract_evolution import (
    ContractEvolutionError,
    ContractVersionConflictError,
    RetiredContractError,
)
from backend.main import app
from backend.use_cases.data_contract.sync_from_github import SyncFromGitHubUseCase
from backend.use_cases.data_contract.update import UpdatedContract
from tests.quality_rule_builders import library_rule

NOW = datetime.now(tz=timezone.utc)
CONTRACT_ID = uuid.uuid4()
DOMAIN_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _contract(**kw) -> DataContract:
    return DataContract(
        id=kw.get("id", CONTRACT_ID),
        title=kw.get("title", "Orders"),
        version="1.0.0",
        owner="alice",
        domain="commerce",
        tier=2,
        status=kw.get("status", "draft"),
        models={"fields": []},
        servicelevels={"properties": [
            {"property": "freshness", "value": 24, "unit": "h"},
            {"property": "availability", "value": 99, "unit": "%"},
        ]},
        domain_id=DOMAIN_ID,
        created_at=NOW,
        updated_at=NOW,
        description=kw.get("description"),
        team_members=kw.get("team_members"),
        support=kw.get("support"),
        servers=kw.get("servers"),
    )


def _user(role: UserRole = UserRole.PLATFORM_ADMIN) -> User:
    return User(id=USER_ID, name="Admin", email=Email("admin@example.com"), role=role)


def _stakeholder() -> ContractStakeholder:
    return ContractStakeholder(
        contract_id=CONTRACT_ID,
        user_id=USER_ID,
        assigned_by=USER_ID,
        assigned_at=NOW,
    )


@pytest.fixture
def admin_client():
    """TestClient authenticated as PLATFORM_ADMIN with a mocked DB."""
    mock_db = AsyncMock()
    admin = _user(UserRole.PLATFORM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db_connection] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ── main.py: custom_openapi ──────────────────────────────────────────────────

def test_openapi_schema_includes_bearer_auth(admin_client):
    resp = admin_client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "BearerAuth" in schema["components"]["securitySchemes"]


def test_openapi_schema_cached_on_second_call(admin_client):
    admin_client.get("/openapi.json")
    resp = admin_client.get("/openapi.json")
    assert resp.status_code == 200


# ── data_contract router ─────────────────────────────────────────────────────

def test_list_data_contracts(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = [_contract()]
    app.dependency_overrides[get_list_data_contracts_use_case] = lambda: mock_uc
    resp = admin_client.get("/api/v1/data-contracts")
    assert resp.status_code == 200
    assert resp.json()[0]["title"] == "Orders"


def test_get_data_contract_found(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _contract()
    mock_sr = AsyncMock()
    mock_sr.is_stakeholder = AsyncMock(return_value=True)
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_uc
    app.dependency_overrides[get_stakeholder_repository] = lambda: mock_sr
    resp = admin_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Orders"


def test_get_data_contract_not_found(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = None
    mock_sr = AsyncMock()
    mock_sr.is_stakeholder = AsyncMock(return_value=False)
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_uc
    app.dependency_overrides[get_stakeholder_repository] = lambda: mock_sr
    resp = admin_client.get(f"/api/v1/data-contracts/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_data_contract_yaml(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _contract()
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_uc
    resp = admin_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}/yaml")
    assert resp.status_code == 200
    assert "Orders" in resp.text


def test_get_data_contract_yaml_not_found(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = None
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_uc
    resp = admin_client.get(f"/api/v1/data-contracts/{uuid.uuid4()}/yaml")
    assert resp.status_code == 404


def test_create_data_contract(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _contract(title="Sales")
    app.dependency_overrides[get_create_data_contract_use_case] = lambda: mock_uc
    resp = admin_client.post("/api/v1/data-contracts", json={
        "title": "Sales",
        "version": "1.0.0",
        "owner": "bob",
        "domain_id": str(DOMAIN_ID),
        "tier": 2,
        "status": "draft",
        "models": {"fields": []},
        "servicelevels": {"properties": [
            {"property": "freshness", "value": 24, "unit": "h"},
            {"property": "availability", "value": 99, "unit": "%"},
        ]},
    })
    assert resp.status_code == 201
    assert resp.json()["title"] == "Sales"


def test_update_data_contract(admin_client):
    mock_update = AsyncMock()
    mock_update.execute.return_value = UpdatedContract(_contract(), _contract(title="Updated"))
    app.dependency_overrides[get_update_data_contract_use_case] = lambda: mock_update
    resp = admin_client.put(f"/api/v1/data-contracts/{CONTRACT_ID}", json={
        "title": "Updated",
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated"


def test_update_data_contract_not_found(admin_client):
    mock_update = AsyncMock()
    mock_update.execute.return_value = None
    app.dependency_overrides[get_update_data_contract_use_case] = lambda: mock_update
    resp = admin_client.put(f"/api/v1/data-contracts/{uuid.uuid4()}", json={
        "title": "X",
    })
    assert resp.status_code == 404


def test_delete_data_contract(admin_client):
    mock_delete = AsyncMock()
    mock_delete.execute.return_value = True
    mock_get = AsyncMock()
    mock_get.execute.return_value = _contract()
    app.dependency_overrides[get_delete_data_contract_use_case] = lambda: mock_delete
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_get
    resp = admin_client.delete(f"/api/v1/data-contracts/{CONTRACT_ID}")
    assert resp.status_code == 204


def test_delete_data_contract_not_found(admin_client):
    mock_delete = AsyncMock()
    mock_delete.execute.return_value = False
    mock_get = AsyncMock()
    mock_get.execute.return_value = _contract()
    app.dependency_overrides[get_delete_data_contract_use_case] = lambda: mock_delete
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_get
    resp = admin_client.delete(f"/api/v1/data-contracts/{CONTRACT_ID}")
    assert resp.status_code == 404


def test_assign_stakeholder(admin_client):
    mock_assign = AsyncMock()
    mock_assign.execute.return_value = _stakeholder()
    mock_get = AsyncMock()
    mock_get.execute.return_value = _contract()
    app.dependency_overrides[get_assign_stakeholder_use_case] = lambda: mock_assign
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_get
    resp = admin_client.post(
        f"/api/v1/data-contracts/{CONTRACT_ID}/stakeholders",
        json={"user_id": str(USER_ID)},
    )
    assert resp.status_code == 201


def test_remove_stakeholder(admin_client):
    mock_remove = AsyncMock()
    mock_remove.execute.return_value = None
    mock_get = AsyncMock()
    mock_get.execute.return_value = _contract()
    app.dependency_overrides[get_remove_stakeholder_use_case] = lambda: mock_remove
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_get
    resp = admin_client.delete(
        f"/api/v1/data-contracts/{CONTRACT_ID}/stakeholders/{USER_ID}"
    )
    assert resp.status_code == 204


# ── users router ─────────────────────────────────────────────────────────────

def test_create_user(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _user()
    app.dependency_overrides[get_create_user_use_case] = lambda: mock_uc
    resp = admin_client.post("/api/v1/users", json={
        "username": "admin",
        "email": "admin@example.com",
        "password": "Str0ng!Pass",
    })
    assert resp.status_code == 201


def test_list_users(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = [_user()]
    app.dependency_overrides[get_list_users_use_case] = lambda: mock_uc
    resp = admin_client.get("/api/v1/users")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_user_found(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _user()
    app.dependency_overrides[get_get_user_use_case] = lambda: mock_uc
    resp = admin_client.get(f"/api/v1/users/{USER_ID}")
    assert resp.status_code == 200


def test_get_user_not_found(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = None
    app.dependency_overrides[get_get_user_use_case] = lambda: mock_uc
    resp = admin_client.get(f"/api/v1/users/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_update_user(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _user()
    app.dependency_overrides[get_update_user_use_case] = lambda: mock_uc
    resp = admin_client.put(f"/api/v1/users/{USER_ID}", json={"username": "newname"})
    assert resp.status_code == 200


def test_update_user_not_found(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = None
    app.dependency_overrides[get_update_user_use_case] = lambda: mock_uc
    resp = admin_client.put(f"/api/v1/users/{uuid.uuid4()}", json={"username": "x"})
    assert resp.status_code == 404


def test_delete_user(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = True
    app.dependency_overrides[get_delete_user_use_case] = lambda: mock_uc
    resp = admin_client.delete(f"/api/v1/users/{USER_ID}")
    assert resp.status_code == 204


def test_delete_user_not_found(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = False
    app.dependency_overrides[get_delete_user_use_case] = lambda: mock_uc
    resp = admin_client.delete(f"/api/v1/users/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_assign_user_role(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _user(UserRole.DATA_STEWARD)
    app.dependency_overrides[get_assign_role_use_case] = lambda: mock_uc
    resp = admin_client.patch(
        f"/api/v1/users/{USER_ID}/role",
        json={"role": "DATA_STEWARD"},
    )
    assert resp.status_code == 200


def test_assign_user_role_invalid(admin_client):
    mock_uc = AsyncMock()
    app.dependency_overrides[get_assign_role_use_case] = lambda: mock_uc
    resp = admin_client.patch(
        f"/api/v1/users/{USER_ID}/role",
        json={"role": "INVALID_ROLE"},
    )
    assert resp.status_code == 400


def test_create_user_value_error(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.side_effect = ValueError("Email already taken")
    app.dependency_overrides[get_create_user_use_case] = lambda: mock_uc
    resp = admin_client.post("/api/v1/users", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "Str0ng!Pass",
    })
    assert resp.status_code == 400
    assert "Email already taken" in resp.json()["detail"]


def test_update_user_value_error(admin_client):
    mock_uc = AsyncMock()
    mock_uc.execute.side_effect = ValueError("Invalid email format")
    app.dependency_overrides[get_update_user_use_case] = lambda: mock_uc
    resp = admin_client.put(f"/api/v1/users/{USER_ID}", json={"email": "bad"})
    assert resp.status_code == 400


def test_get_user_domains(admin_client):
    domain_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_db.fetch.return_value = [{"id": domain_id, "name": "Finance"}]
    app.dependency_overrides[get_db_connection] = lambda: mock_db
    resp = admin_client.get(f"/api/v1/users/{USER_ID}/domains")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Finance"


def test_get_user_domains_empty(admin_client):
    mock_db = AsyncMock()
    mock_db.fetch.return_value = []
    app.dependency_overrides[get_db_connection] = lambda: mock_db
    resp = admin_client.get(f"/api/v1/users/{USER_ID}/domains")
    assert resp.status_code == 200
    assert resp.json() == []


def test_yaml_with_quality_data(admin_client):
    contract = _contract()
    contract.models = {
        "fields": [{"name": "id", "type": "string"}],
        "quality": [library_rule(column="id", description="Must be complete")],
    }
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = contract
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_uc
    resp = admin_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}/yaml")
    assert resp.status_code == 200
    assert "metric: nullValues" in resp.text


# ── sync endpoint ─────────────────────────────────────────────────────────────

def test_sync_no_github_returns_503(admin_client):
    app.dependency_overrides[get_github_client] = lambda: None
    resp = admin_client.post("/api/v1/data-contracts/sync")
    assert resp.status_code == 503


def test_sync_with_github_returns_result(admin_client):
    mock_github = AsyncMock()
    mock_github.list_all_yaml_contents.return_value = []
    app.dependency_overrides[get_github_client] = lambda: mock_github
    app.dependency_overrides[get_data_contract_repository] = lambda: AsyncMock()
    app.dependency_overrides[get_domain_repository] = lambda: AsyncMock()
    resp = admin_client.post("/api/v1/data-contracts/sync")
    assert resp.status_code == 200
    assert resp.json() == {"created": 0, "updated": 0, "errors": []}


# ── DATA_STEWARD stakeholder paths ────────────────────────────────────────────

def _steward_client():
    return _user(UserRole.DATA_STEWARD)


def test_assign_stakeholder_steward_contract_not_found(admin_client):
    app.dependency_overrides[get_current_user] = lambda: _steward_client()
    mock_get = AsyncMock()
    mock_get.execute.return_value = None
    mock_assign = AsyncMock()
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_get
    app.dependency_overrides[get_assign_stakeholder_use_case] = lambda: mock_assign
    resp = admin_client.post(
        f"/api/v1/data-contracts/{CONTRACT_ID}/stakeholders",
        json={"user_id": str(USER_ID)},
    )
    assert resp.status_code == 404


def test_remove_stakeholder_steward_contract_not_found(admin_client):
    app.dependency_overrides[get_current_user] = lambda: _steward_client()
    mock_get = AsyncMock()
    mock_get.execute.return_value = None
    mock_remove = AsyncMock()
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_get
    app.dependency_overrides[get_remove_stakeholder_use_case] = lambda: mock_remove
    resp = admin_client.delete(
        f"/api/v1/data-contracts/{CONTRACT_ID}/stakeholders/{USER_ID}"
    )
    assert resp.status_code == 404


# ── data_contract.py: YAML endpoint stakeholder restriction ──────────────────

@pytest.fixture
def consumer_client():
    """TestClient authenticated as DATA_CONSUMER with a mocked DB."""
    mock_db = AsyncMock()
    consumer = _user(UserRole.DATA_CONSUMER)
    app.dependency_overrides[get_current_user] = lambda: consumer
    app.dependency_overrides[get_db_connection] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


STORED = dict(
    description={"purpose": "p", "usage": "u", "limitations": ""},
    team_members=[{"username": "alice", "name": "", "role": "owner"}],
    support=[{"channel": "#c", "url": "", "tool": "slack", "scope": ""}],
    servers=[{"server": "dev", "type": "local", "environment": "", "host": "", "catalog": "",
              "schema_name": "", "port": None, "database": "", "location": "", "format": "csv",
              "path": "./a.csv"}],
)


def _put(admin_client, body):
    mock_update = AsyncMock()
    stored = _contract(**STORED)
    mock_update.execute.return_value = UpdatedContract(stored, stored)
    app.dependency_overrides[get_update_data_contract_use_case] = lambda: mock_update
    resp = admin_client.put(f"/api/v1/data-contracts/{CONTRACT_ID}", json=body)
    return resp, mock_update.execute.call_args.kwargs["changes"]


def test_update_empty_list_clears_only_that_section(admin_client):
    _, changes = _put(admin_client, {"servers": []})
    assert changes["servers"] == [] and "team_members" not in changes


def test_update_replaces_description_whole(admin_client):
    _, changes = _put(admin_client, {"description": {"purpose": "new"}})
    assert changes["description"] == {"purpose": "new", "usage": "", "limitations": ""}


def _post(admin_client, extra):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _contract()
    app.dependency_overrides[get_create_data_contract_use_case] = lambda: mock_uc
    body = {"title": "S", "owner": "o", "domain_id": str(DOMAIN_ID), "tier": 3, **extra}
    return admin_client.post("/api/v1/data-contracts", json=body), mock_uc


def test_create_passes_metadata_and_dumps_rows(admin_client):
    resp, mock_uc = _post(admin_client, {"team_members": [{"username": "alice"}]})
    assert resp.status_code == 201
    kwargs = mock_uc.execute.call_args.kwargs
    assert kwargs["team_members"] == [{"username": "alice", "name": "", "role": ""}]
    assert kwargs["description"] == {"purpose": "", "usage": "", "limitations": ""}
    assert kwargs["servers"] == []


def test_create_rejects_a_password_on_a_server(admin_client):
    resp, mock_uc = _post(admin_client, {"servers": [{"server": "a", "type": "local", "path": "./a",
                                                      "format": "csv", "password": "not-a-real-secret"}]})
    assert resp.status_code == 422
    mock_uc.execute.assert_not_called()


def _post_contract(admin_client, models, servicelevels):
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _contract(title="Sales")
    app.dependency_overrides[get_create_data_contract_use_case] = lambda: mock_uc
    resp = admin_client.post("/api/v1/data-contracts", json={
        "title": "Sales", "owner": "bob", "domain_id": str(DOMAIN_ID), "tier": 2,
        "models": models, "servicelevels": servicelevels,
    })
    return resp, mock_uc


def test_create_with_library_rule_and_structured_sla(admin_client):
    sla = {"properties": [{"property": "freshness", "value": 24, "unit": "h"}]}
    resp, mock_uc = _post_contract(
        admin_client,
        {"fields": [{"name": "email", "type": "string"}],
         "quality": [library_rule(operator="mustBeLessOrEqualTo", value=1, unit="percent")]},
        sla,
    )
    assert resp.status_code == 201
    assert mock_uc.execute.call_args.kwargs["servicelevels"] == sla
    assert mock_uc.execute.call_args.kwargs["models"]["quality"][0]["type"] == "library"


def test_create_rejects_two_rules_on_same_metric_and_column(admin_client):
    resp, mock_uc = _post_contract(
        admin_client,
        {"fields": [{"name": "email", "type": "string"}],
         "quality": [library_rule(), library_rule(operator="mustBeLessThan", value=5)]},
        {"properties": []},
    )
    assert resp.status_code == 422
    assert "cannot run two" in resp.text
    mock_uc.execute.assert_not_called()


VIOLATION = (
    "Contract changes require a MAJOR version bump (current 1.0.0, requested 1.0.1):"
    " property 'amount' removed"
)


def _put_contract(admin_client, body, *, side_effect=None, result=None):
    mock_get, mock_update, github = AsyncMock(), AsyncMock(), AsyncMock()
    github.contract_path = MagicMock(
        side_effect=lambda domain, title: f"contracts/{domain}/{title.lower()}.yaml")
    mock_get.execute.return_value = _contract()
    mock_update.execute.return_value = result or UpdatedContract(_contract(), _contract())
    if side_effect is not None:
        mock_update.execute.side_effect = side_effect
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_get
    app.dependency_overrides[get_update_data_contract_use_case] = lambda: mock_update
    app.dependency_overrides[get_github_client] = lambda: github
    resp = admin_client.put(f"/api/v1/data-contracts/{CONTRACT_ID}", json=body)
    return resp, mock_update, github


@pytest.mark.parametrize("error", [
    ContractEvolutionError(VIOLATION),
    ContractVersionConflictError("Version 1.1.0 already exists for this contract"),
    RetiredContractError("retired"),
], ids=["policy", "conflict", "retired"])
def test_update_policy_rejection_returns_409_and_skips_github(admin_client, error):
    resp, _, github = _put_contract(admin_client, {"version": "1.0.1"}, side_effect=error)
    assert resp.status_code == 409
    assert resp.json()["detail"] == str(error)
    github.push.assert_not_called()


def test_update_invalid_version_returns_400(admin_client):
    error = ValueError("Version '1.1' must match MAJOR.MINOR.PATCH")
    resp, _, _ = _put_contract(admin_client, {"version": "1.1"}, side_effect=error)
    assert resp.status_code == 400


def test_status_only_put_sends_only_the_status(admin_client):
    # The use case merges the rest under its row lock, never from a stale read.
    resp, mock_update, _ = _put_contract(admin_client, {"status": "active"})
    assert resp.status_code == 200
    kwargs = mock_update.execute.call_args.kwargs
    assert kwargs["changes"] == {"status": "active"}
    assert kwargs["created_by"] == USER_ID


@pytest.mark.parametrize("member, status", [(True, 200), (False, 403)])
def test_steward_updates_only_a_contract_of_their_domain(admin_client, member, status):
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.DATA_STEWARD)
    db = AsyncMock()
    db.fetchrow.return_value = {"?column?": 1} if member else None
    app.dependency_overrides[get_db_connection] = lambda: db
    resp, mock_update, _ = _put_contract(admin_client, {"title": "Orders"})
    assert resp.status_code == status
    assert mock_update.execute.called is member


def test_rename_removes_the_file_at_the_locked_path(admin_client):
    renamed = UpdatedContract(_contract(), _contract(title="Invoices"))
    resp, _, github = _put_contract(admin_client, {"title": "Invoices"}, result=renamed)
    assert resp.status_code == 200
    github.delete.assert_called_once_with(
        "contracts/commerce/orders.yaml", "Remove stale contract file: Orders")


def test_update_accepts_retired_status(admin_client):
    resp, _, _ = _put_contract(admin_client, {"status": "retired"})
    assert resp.status_code == 200


def test_create_rejects_retired_status(admin_client):
    mock_uc = AsyncMock()
    app.dependency_overrides[get_create_data_contract_use_case] = lambda: mock_uc
    resp = admin_client.post("/api/v1/data-contracts", json={
        "title": "Sales", "owner": "bob", "domain_id": str(DOMAIN_ID), "tier": 2,
        "status": "retired",
    })
    assert resp.status_code == 422
    mock_uc.execute.assert_not_called()


def test_create_passes_the_user_to_the_snapshot(admin_client):
    resp, mock_uc = _post_contract(admin_client, {"fields": []}, {"properties": []})
    assert resp.status_code == 201
    assert mock_uc.execute.call_args.kwargs["created_by"] == USER_ID


def test_sync_passes_the_admin_id(admin_client, monkeypatch):
    execute = AsyncMock(return_value={"created": 0, "updated": 0, "errors": []})
    monkeypatch.setattr(SyncFromGitHubUseCase, "execute", execute)
    app.dependency_overrides[get_github_client] = lambda: AsyncMock()
    app.dependency_overrides[get_data_contract_repository] = lambda: AsyncMock()
    app.dependency_overrides[get_domain_repository] = lambda: AsyncMock()
    resp = admin_client.post("/api/v1/data-contracts/sync")
    assert resp.status_code == 200
    assert execute.call_args.kwargs["created_by"] == USER_ID


LIST_PATH = f"/api/v1/data-contracts/{CONTRACT_ID}/versions"
YAML_PATH = f"/api/v1/data-contracts/{CONTRACT_ID}/versions/1.0.0/yaml"
VERSION_YAML = "apiVersion: v3.2.0\nversion: 1.0.0\n"


def _versions():
    return [ContractVersion(CONTRACT_ID, "1.1.0", USER_ID, NOW),
            ContractVersion(CONTRACT_ID, "1.0.0", None, NOW)]


def _version_reads(yaml_text=VERSION_YAML, stakeholder=True):
    get_uc, list_uc, yaml_uc, sr = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    get_uc.execute.return_value = _contract()
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: get_uc
    list_uc.execute.return_value = _versions()
    yaml_uc.execute.return_value = yaml_text
    sr.is_stakeholder = AsyncMock(return_value=stakeholder)
    app.dependency_overrides[get_list_contract_versions_use_case] = lambda: list_uc
    app.dependency_overrides[get_get_contract_version_yaml_use_case] = lambda: yaml_uc
    app.dependency_overrides[get_stakeholder_repository] = lambda: sr
    return list_uc, yaml_uc


def test_list_versions(admin_client):
    _version_reads()
    resp = admin_client.get(LIST_PATH)
    assert resp.status_code == 200
    body = resp.json()
    assert [v["version"] for v in body] == ["1.1.0", "1.0.0"]
    assert body[1]["created_by"] is None
    assert "yaml_content" not in body[0]


def test_list_versions_unknown_contract_is_404(admin_client):
    list_uc, _ = _version_reads()
    list_uc.execute.return_value = None
    assert admin_client.get(LIST_PATH).status_code == 404


def test_get_version_yaml(admin_client):
    _version_reads()
    resp = admin_client.get(YAML_PATH)
    assert resp.status_code == 200
    assert resp.text == VERSION_YAML
    assert resp.headers["content-type"].startswith("text/plain")


def test_get_version_yaml_unknown_version_is_404(admin_client):
    _version_reads(yaml_text=None)
    assert admin_client.get(YAML_PATH).status_code == 404


def test_sync_read_failure_returns_502(admin_client):
    github = AsyncMock()
    github.list_all_yaml_contents.side_effect = RuntimeError("GitHub API 301: Moved")
    app.dependency_overrides[get_github_client] = lambda: github
    app.dependency_overrides[get_data_contract_repository] = lambda: AsyncMock()
    app.dependency_overrides[get_domain_repository] = lambda: AsyncMock()
    resp = admin_client.post("/api/v1/data-contracts/sync")
    assert resp.status_code == 502
    assert "301" in resp.json()["detail"]


# ── Contract access layers: readers ──────────────────────────────────────────

DRAFT_MESSAGE = (
    "This contract is a draft. Only its domain and invited reviewers can read it."
)
READ_PATHS = ["", "/yaml", "/versions", "/versions/1.0.0/yaml"]
OTHER_DOMAIN_ID = uuid.uuid4()


def _as(role: UserRole, member_domains=()):
    """Act as `role`, a member of `member_domains` (membership answered by the db)."""
    db = AsyncMock()
    domains = set(member_domains)

    async def fetchrow(_sql, _user_id, domain_id, *args):
        return {"?column?": 1} if domain_id in domains else None

    db.fetchrow = AsyncMock(side_effect=fetchrow)
    db.fetch = AsyncMock(return_value=[{"domain_id": d} for d in domains])
    app.dependency_overrides[get_current_user] = lambda: _user(role)
    app.dependency_overrides[get_db_connection] = lambda: db
    return db


def _reads(contract, stakeholder=False):
    get_uc, list_uc, yaml_uc, sr = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    get_uc.execute.return_value = contract
    list_uc.execute.return_value = _versions()
    yaml_uc.execute.return_value = VERSION_YAML
    sr.is_stakeholder = AsyncMock(return_value=stakeholder)
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: get_uc
    app.dependency_overrides[get_list_contract_versions_use_case] = lambda: list_uc
    app.dependency_overrides[get_get_contract_version_yaml_use_case] = lambda: yaml_uc
    app.dependency_overrides[get_stakeholder_repository] = lambda: sr
    return sr, list_uc, yaml_uc


def _list(contracts, stakeholder_of=()):
    uc, sr = AsyncMock(), AsyncMock()
    uc.execute.return_value = contracts
    sr.contract_ids_of = AsyncMock(return_value=set(stakeholder_of))
    app.dependency_overrides[get_list_data_contracts_use_case] = lambda: uc
    app.dependency_overrides[get_stakeholder_repository] = lambda: sr
    return sr


def _in_domain(contract: DataContract, domain_id: uuid.UUID) -> DataContract:
    contract.domain_id = domain_id
    return contract


@pytest.mark.parametrize("status", ["active", "deprecated", "retired"])
@pytest.mark.parametrize("path", READ_PATHS)
def test_consumer_reads_a_published_contract(consumer_client, path, status):
    sr, _, _ = _reads(_contract(status=status))
    resp = consumer_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}{path}")
    assert resp.status_code == 200
    sr.is_stakeholder.assert_not_called()


@pytest.mark.parametrize("status", ["draft", "in_review"])
@pytest.mark.parametrize("path", READ_PATHS)
def test_consumer_outside_a_draft_gets_the_draft_message(consumer_client, path, status):
    _, list_uc, yaml_uc = _reads(_contract(status=status), stakeholder=False)
    resp = consumer_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}{path}")
    assert resp.status_code == 403
    assert resp.json()["detail"] == DRAFT_MESSAGE
    list_uc.execute.assert_not_called()
    yaml_uc.execute.assert_not_called()


@pytest.mark.parametrize("path", READ_PATHS)
def test_invited_consumer_reads_the_draft(consumer_client, path):
    _reads(_contract(status="in_review"), stakeholder=True)
    resp = consumer_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}{path}")
    assert resp.status_code == 200


def test_member_consumer_does_not_read_a_draft(consumer_client):
    _as(UserRole.DATA_CONSUMER, member_domains={DOMAIN_ID})
    _reads(_contract(status="draft"), stakeholder=False)
    resp = consumer_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}")
    assert resp.status_code == 403


@pytest.mark.parametrize("role", [UserRole.DATA_STEWARD, UserRole.DATA_OWNER])
@pytest.mark.parametrize("member, code", [(True, 200), (False, 403)])
def test_the_domain_reads_its_drafts(consumer_client, role, member, code):
    _as(role, member_domains={DOMAIN_ID} if member else ())
    _reads(_contract(status="draft"), stakeholder=False)
    resp = consumer_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}")
    assert resp.status_code == code


def test_unknown_contract_is_404_before_any_access_check(consumer_client):
    sr, list_uc, _ = _reads(None)
    resp = consumer_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}/versions")
    assert resp.status_code == 404
    sr.is_stakeholder.assert_not_called()
    list_uc.execute.assert_not_called()


def test_list_shows_published_in_full_and_hides_unreadable_drafts(consumer_client):
    published = _contract(id=uuid.uuid4(), status="active", **STORED)
    draft = _contract(id=uuid.uuid4(), status="draft")
    invited = _contract(id=uuid.uuid4(), status="in_review")
    _list([published, draft, invited], stakeholder_of={invited.id})
    listed = consumer_client.get("/api/v1/data-contracts").json()
    assert [c["id"] for c in listed] == [str(published.id), str(invited.id)]
    for key in ("team_members", "support", "servers"):
        assert listed[0][key] == STORED[key]


def test_list_shows_a_steward_the_drafts_of_their_domain(consumer_client):
    _as(UserRole.DATA_STEWARD, member_domains={DOMAIN_ID})
    mine = _contract(id=uuid.uuid4(), status="draft")
    other = _in_domain(_contract(id=uuid.uuid4(), status="draft"), OTHER_DOMAIN_ID)
    _list([mine, other])
    listed = consumer_client.get("/api/v1/data-contracts").json()
    assert [c["id"] for c in listed] == [str(mine.id)]


def test_list_hides_domain_drafts_from_a_member_consumer(consumer_client):
    _as(UserRole.DATA_CONSUMER, member_domains={DOMAIN_ID})
    _list([_contract(status="draft")])
    assert consumer_client.get("/api/v1/data-contracts").json() == []


def test_list_of_published_contracts_asks_nothing_more(consumer_client):
    db = _as(UserRole.DATA_STEWARD)
    sr = _list([_contract(status="active"), _contract(id=uuid.uuid4(), status="retired")])
    assert len(consumer_client.get("/api/v1/data-contracts").json()) == 2
    sr.contract_ids_of.assert_not_called()
    db.fetch.assert_not_called()


def test_admin_lists_every_draft_without_access_queries(admin_client):
    sr = _list([_contract(status="draft"), _contract(id=uuid.uuid4(), status="in_review")])
    assert len(admin_client.get("/api/v1/data-contracts").json()) == 2
    sr.contract_ids_of.assert_not_called()
