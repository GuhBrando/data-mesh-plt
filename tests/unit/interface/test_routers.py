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
