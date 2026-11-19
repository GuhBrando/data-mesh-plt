import uuid
from typing import get_args

import pytest
from pydantic import ValidationError

from backend.domain.contract_metadata import SERVER_TYPES
from backend.domain.contract_values import (
    CLASSIFICATIONS,
    CONTRACT_STATUSES,
    FIELD_TYPES,
    RULE_DIMENSIONS,
    RULE_OPERATORS,
    SLA_KEYS,
)
from backend.interface.schemas.data_contract import (
    ContractDescription,
    ContractServer,
    DataContractCreateModel,
    QualityRule,
    SchemaField,
    ServiceLevels,
    SupportChannel,
    TeamMember,
)

DOMAIN_ID = uuid.uuid4()


def test_valid_create_model():
    m = DataContractCreateModel(
        title="Orders",
        owner="alice",
        domain_id=DOMAIN_ID,
        tier=2,
    )
    assert m.version == "1.0.0"
    assert m.status == "draft"
    assert m.models.fields == []


def test_tier_below_range_rejected():
    with pytest.raises(ValidationError):
        DataContractCreateModel(title="x", owner="o", domain_id=DOMAIN_ID, tier=0)


def test_tier_above_range_rejected():
    with pytest.raises(ValidationError):
        DataContractCreateModel(title="x", owner="o", domain_id=DOMAIN_ID, tier=5)


def test_invalid_status_rejected():
    with pytest.raises(ValidationError):
        DataContractCreateModel(
            title="x", owner="o", domain_id=DOMAIN_ID, tier=1, status="unknown"
        )


def test_schema_field_defaults():
    m = DataContractCreateModel(title="x", owner="o", domain_id=DOMAIN_ID, tier=3)
    assert m.servicelevels.freshness == ""
    assert m.servicelevels.availability == ""


def test_schema_field_attributes():
    f = SchemaField(name="a", type="string")
    assert (f.classification, f.unique, f.physical_type) == ("", False, "")
    for value in ("public", "internal", "confidential", "restricted"):
        assert SchemaField(name="a", type="string", classification=value).classification == value
    with pytest.raises(ValidationError):
        SchemaField(name="a", type="string", classification="secret")


@pytest.mark.parametrize("build", [
    lambda: TeamMember(username="  "),
    lambda: SupportChannel(channel=""),
    lambda: ContractServer(server=" ", type="local", path="./a", format="csv"),
    lambda: ContractServer(server="a", type="local", path="./a", format="csv", password="not-a-real-secret"),
    lambda: ContractServer(server="a", type="databricks", catalog="c", schema="s"),
    lambda: TeamMember(username="a", dateIn="2026-01-01"),
    lambda: SupportChannel(channel="c", invitationUrl="https://example.com"),
    lambda: SupportChannel(channel="c", url="javascript:alert(1)"),
    lambda: ContractDescription(purpose="p", customProperties=[]),
])
def test_invalid_rows_are_rejected(build):
    with pytest.raises(ValidationError):
        build()


def test_server_applies_the_type_rules():
    with pytest.raises(ValidationError, match="host"):
        ContractServer(server="a", type="azure", location="az://a/b", format="csv", host="h.example.com")


def test_schema_literals_match_the_domain_values():
    def literal(model, name):
        return get_args(model.model_fields[name].annotation)

    assert literal(DataContractCreateModel, "status") == CONTRACT_STATUSES
    assert literal(SchemaField, "type") == FIELD_TYPES
    assert literal(QualityRule, "dimension") == RULE_DIMENSIONS
    assert literal(QualityRule, "operator") == RULE_OPERATORS
    assert tuple(ServiceLevels.model_fields) == SLA_KEYS
    assert literal(SchemaField, "classification") == ("", *CLASSIFICATIONS)
    assert literal(ContractServer, "type") == SERVER_TYPES
