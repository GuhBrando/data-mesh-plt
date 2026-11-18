"""
Router integration tests using FastAPI's TestClient with dependency overrides.
Covers data_contract and users router endpoints plus main.py custom_openapi.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.domain.entities.contract_stakeholder import ContractStakeholder
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
    get_github_client,
    get_list_data_contracts_use_case,
    get_list_users_use_case,
    get_remove_stakeholder_use_case,
    get_stakeholder_repository,
    get_update_data_contract_use_case,
    get_update_user_use_case,
    get_user_repository,
)
from backend.interface.security import get_current_user
from backend.main import app
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
        status="draft",
        models={"fields": []},
        servicelevels={
            "freshness": "24h", "availability": "99%",
            "retention": "365d", "latency": "1h",
        },
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
        "servicelevels": {"freshness": "24h", "availability": "99%",
                          "retention": "365d", "latency": "1h"},
    })
    assert resp.status_code == 201
    assert resp.json()["title"] == "Sales"


def test_update_data_contract(admin_client):
    contract = _contract()
    mock_get = AsyncMock()
    mock_get.execute.return_value = contract
    mock_update = AsyncMock()
    mock_update.execute.return_value = _contract(title="Updated")
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_get
    app.dependency_overrides[get_update_data_contract_use_case] = lambda: mock_update
    resp = admin_client.put(f"/api/v1/data-contracts/{CONTRACT_ID}", json={
        "title": "Updated",
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated"


def test_update_data_contract_not_found(admin_client):
    mock_get = AsyncMock()
    mock_get.execute.return_value = None
    mock_update = AsyncMock()
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_get
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
    contract.models = {"fields": [], "quality": [
        {"dimension": "completeness", "column": "id", "operator": ">=",
         "threshold": "0.99", "description": "Must be complete"}
    ]}
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = contract
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_uc
    resp = admin_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}/yaml")
    assert resp.status_code == 200
    assert "quality" in resp.text


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


def test_get_data_contract_yaml_forbidden_for_non_stakeholder_consumer(
    consumer_client,
):
    """A DATA_CONSUMER who is not a stakeholder must not read the ODCS YAML.

    The YAML is a superset of the JSON detail endpoint, which already returns
    403 for this caller. Both endpoints must agree.
    """
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _contract()
    mock_sr = AsyncMock()
    mock_sr.is_stakeholder = AsyncMock(return_value=False)
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_uc
    app.dependency_overrides[get_stakeholder_repository] = lambda: mock_sr
    resp = consumer_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}/yaml")
    assert resp.status_code == 403


def test_get_data_contract_yaml_allowed_for_stakeholder_consumer(consumer_client):
    """A DATA_CONSUMER who is a registered stakeholder keeps YAML access."""
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = _contract()
    mock_sr = AsyncMock()
    mock_sr.is_stakeholder = AsyncMock(return_value=True)
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_uc
    app.dependency_overrides[get_stakeholder_repository] = lambda: mock_sr
    resp = consumer_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}/yaml")
    assert resp.status_code == 200
    assert "Orders" in resp.text


STORED = dict(
    description={"purpose": "p", "usage": "u", "limitations": ""},
    team_members=[{"username": "alice", "name": "", "role": "owner"}],
    support=[{"channel": "#c", "url": "", "tool": "slack", "scope": ""}],
    servers=[{"server": "dev", "type": "local", "environment": "", "host": "", "catalog": "",
              "schema_name": "", "port": None, "database": "", "location": "", "format": "csv",
              "path": "./a.csv"}],
)


def _put(admin_client, body):
    mock_get, mock_update = AsyncMock(), AsyncMock()
    mock_get.execute.return_value = _contract(**STORED)
    mock_update.execute.return_value = _contract(**STORED)
    app.dependency_overrides[get_get_data_contract_use_case] = lambda: mock_get
    app.dependency_overrides[get_update_data_contract_use_case] = lambda: mock_update
    resp = admin_client.put(f"/api/v1/data-contracts/{CONTRACT_ID}", json=body)
    return resp, mock_update.execute.call_args


def test_update_keeps_metadata_when_body_omits_it(admin_client):
    resp, call = _put(admin_client, {"status": "active"})
    assert resp.status_code == 200
    assert {k: call.kwargs[k] for k in STORED} == STORED
    assert {k: resp.json()[k] for k in STORED} == STORED


def test_update_empty_list_clears_only_that_section(admin_client):
    _, call = _put(admin_client, {"servers": []})
    assert call.kwargs["servers"] == [] and call.kwargs["team_members"] == STORED["team_members"]


def test_update_replaces_description_whole(admin_client):
    _, call = _put(admin_client, {"description": {"purpose": "new"}})
    assert call.kwargs["description"] == {"purpose": "new", "usage": "", "limitations": ""}


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
