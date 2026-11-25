"""
Verify that each entity constructor correctly stores every field.
These tests kill mutations that swap or remove field assignments.
"""
import uuid
from datetime import datetime, timezone

import pytest

from backend.domain.entities.contract_stakeholder import ContractStakeholder
from backend.domain.entities.data_contract import DataContract
from backend.domain.entities.domain import Domain
from backend.domain.entities.refresh_token import RefreshToken
from backend.domain.entities.user import User
from backend.domain.value_objects.email import Email
from backend.domain.value_objects.user_role import UserRole

NOW = datetime.now(tz=timezone.utc)


# ── ContractStakeholder ──────────────────────────────────────────────────────

def test_contract_stakeholder_stores_all_fields():
    cid, uid, aid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    s = ContractStakeholder(contract_id=cid, user_id=uid, assigned_by=aid, assigned_at=NOW)
    assert s.contract_id == cid
    assert s.user_id == uid
    assert s.assigned_by == aid
    assert s.assigned_at == NOW


def test_contract_stakeholder_assigned_by_can_be_none():
    cid, uid = uuid.uuid4(), uuid.uuid4()
    s = ContractStakeholder(contract_id=cid, user_id=uid, assigned_by=None, assigned_at=NOW)
    assert s.assigned_by is None


# ── DataContract ─────────────────────────────────────────────────────────────

def test_data_contract_stores_all_fields():
    cid = uuid.uuid4()
    did = uuid.uuid4()
    models = {"fields": [{"name": "id"}]}
    sla = {"freshness": "24h", "availability": "99%", "retention": "365d", "latency": "1h"}
    c = DataContract(
        id=cid, title="Orders", version="2.0.0", owner="alice", domain="commerce",
        tier=1, status="active", models=models, servicelevels=sla,
        created_at=NOW, updated_at=NOW, domain_id=did,
    )
    assert c.id == cid
    assert c.title == "Orders"
    assert c.version == "2.0.0"
    assert c.owner == "alice"
    assert c.domain == "commerce"
    assert c.tier == 1
    assert c.status == "active"
    assert c.models is models
    assert c.servicelevels is sla
    assert c.created_at == NOW
    assert c.updated_at == NOW
    assert c.domain_id == did


def test_data_contract_domain_id_defaults_to_none():
    c = DataContract(
        id=uuid.uuid4(), title="T", version="1", owner="o", domain="d",
        tier=3, status="draft", models={}, servicelevels={},
        created_at=NOW, updated_at=NOW,
    )
    assert c.domain_id is None


# ── Domain ───────────────────────────────────────────────────────────────────

def test_domain_stores_all_fields():
    did = uuid.uuid4()
    d = Domain(id=did, name="Finance")
    assert d.id == did
    assert d.name == "Finance"


def test_domain_repr_contains_id_and_name():
    did = uuid.uuid4()
    d = Domain(id=did, name="Marketing")
    r = repr(d)
    assert str(did) in r
    assert "Marketing" in r


# ── RefreshToken ─────────────────────────────────────────────────────────────

def test_refresh_token_stores_all_fields():
    tid, uid = uuid.uuid4(), uuid.uuid4()
    rt = RefreshToken(id=tid, user_id=uid, token_hash="abc123", expires_at=NOW, revoked=False)
    assert rt.id == tid
    assert rt.user_id == uid
    assert rt.token_hash == "abc123"
    assert rt.expires_at == NOW
    assert rt.revoked is False


def test_refresh_token_revoked_flag_is_stored():
    rt = RefreshToken(id=uuid.uuid4(), user_id=uuid.uuid4(), token_hash="x", expires_at=NOW, revoked=True)
    assert rt.revoked is True


# ── User ─────────────────────────────────────────────────────────────────────

def test_user_stores_all_fields():
    uid = uuid.uuid4()
    email = Email("alice@example.com")
    u = User(id=uid, name="Alice", email=email, password_hash="hashed!", role=UserRole.DATA_OWNER)
    assert u.id == uid
    assert u.name == "Alice"
    assert u.email is email
    assert u.password_hash == "hashed!"
    assert u.role == UserRole.DATA_OWNER


def test_user_password_hash_defaults_to_empty_string():
    u = User(id=uuid.uuid4(), name="Bob", email=Email("bob@example.com"))
    assert u.password_hash == ""


def test_user_role_defaults_to_data_consumer():
    u = User(id=uuid.uuid4(), name="Carol", email=Email("carol@example.com"))
    assert u.role == UserRole.DATA_CONSUMER


def test_user_repr_contains_name_and_role():
    u = User(id=uuid.uuid4(), name="Dave", email=Email("dave@example.com"), role=UserRole.PLATFORM_ADMIN)
    r = repr(u)
    assert "Dave" in r
    assert "PLATFORM_ADMIN" in r


# ── Email value object ───────────────────────────────────────────────────────

def test_email_equal_to_same_address():
    assert Email("a@b.com") == Email("a@b.com")


def test_email_not_equal_to_different_address():
    assert Email("a@b.com") != Email("c@d.com")


def test_email_not_equal_to_plain_string():
    assert Email("a@b.com") != "a@b.com"


def test_email_not_equal_to_non_email_type():
    assert not (Email("a@b.com") == 42)


def test_email_repr_is_the_address():
    assert repr(Email("x@y.com")) == "x@y.com"


def test_email_rejects_invalid_address():
    with pytest.raises(ValueError):
        Email("not-an-email")


# ── UserRole enum ─────────────────────────────────────────────────────────────

def test_user_role_platform_admin_value():
    assert UserRole.PLATFORM_ADMIN.value == "PLATFORM_ADMIN"


def test_user_role_data_owner_value():
    assert UserRole.DATA_OWNER.value == "DATA_OWNER"


def test_user_role_data_steward_value():
    assert UserRole.DATA_STEWARD.value == "DATA_STEWARD"


def test_user_role_data_consumer_value():
    assert UserRole.DATA_CONSUMER.value == "DATA_CONSUMER"
