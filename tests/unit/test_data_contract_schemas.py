import uuid

import pytest
from pydantic import ValidationError

from backend.interface.schemas.data_contract import DataContractCreateModel

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


def test_schema_literals_match_the_domain_values():
    from typing import get_args

    from backend.domain.contract_values import (
        CONTRACT_STATUSES,
        FIELD_TYPES,
        RULE_DIMENSIONS,
        RULE_OPERATORS,
        SLA_KEYS,
    )
    from backend.interface.schemas.data_contract import (
        QualityRule,
        SchemaField,
        ServiceLevels,
    )

    def literal(model, name):
        return get_args(model.model_fields[name].annotation)

    assert literal(DataContractCreateModel, "status") == CONTRACT_STATUSES
    assert literal(SchemaField, "type") == FIELD_TYPES
    assert literal(QualityRule, "dimension") == RULE_DIMENSIONS
    assert literal(QualityRule, "operator") == RULE_OPERATORS
    assert tuple(ServiceLevels.model_fields) == SLA_KEYS
