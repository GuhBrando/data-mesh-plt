import uuid

import pytest
from pydantic import ValidationError

from backend.interface.schemas.data_contract import (
    DataContractCreateModel,
    ModelsSection,
    ServiceLevels,
)
from tests.quality_rule_builders import library_rule

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
    assert m.servicelevels.properties == []


from typing import get_args

from backend.domain.contract_metadata import CLASSIFICATIONS, SERVER_TYPES
from backend.interface.schemas.data_contract import (
    ContractServer, DataContractUpdateModel, SchemaField, SupportChannel, TeamMember,
)


def test_create_model_defaults_new_sections():
    m = DataContractCreateModel(title="x", owner="o", domain_id=DOMAIN_ID, tier=3)
    assert m.description.model_dump() == {"purpose": "", "usage": "", "limitations": ""}
    assert m.team_members == [] and m.support == [] and m.servers == []
    u = DataContractUpdateModel()
    assert (u.description, u.team_members, u.support, u.servers) == (None, None, None, None)


def test_schema_field_attributes():
    f = SchemaField(name="a", type="string")
    assert (f.classification, f.unique, f.physical_type) == ("", False, "")
    for value in ("public", "internal", "confidential", "restricted"):
        assert SchemaField(name="a", type="string", classification=value).classification == value
    with pytest.raises(ValidationError):
        SchemaField(name="a", type="string", classification="secret")


def test_literals_match_the_domain_constants():
    assert set(get_args(SchemaField.model_fields["classification"].annotation)) == {"", *CLASSIFICATIONS}
    assert set(get_args(ContractServer.model_fields["type"].annotation)) == set(SERVER_TYPES)


@pytest.mark.parametrize("build", [
    lambda: TeamMember(username="  "),
    lambda: SupportChannel(channel=""),
    lambda: ContractServer(server=" ", type="local", path="./a", format="csv"),
    lambda: ContractServer(server="a", type="local", path="./a", format="csv", password="not-a-real-secret"),
    lambda: ContractServer(server="a", type="databricks", catalog="c", schema="s"),
])
def test_invalid_rows_are_rejected(build):
    with pytest.raises(ValidationError):
        build()


def test_server_applies_the_type_rules():
    with pytest.raises(ValidationError, match="host"):
        ContractServer(server="a", type="azure", location="az://a/b", format="csv", host="h.example.com")


def test_new_rule_and_service_levels_are_accepted():
    m = DataContractCreateModel(
        title="x", owner="o", domain_id=DOMAIN_ID, tier=2,
        models={
            "fields": [{"name": "email", "type": "string"}],
            "quality": [
                library_rule(unit="percent", operator="mustBeLessOrEqualTo", value=1)
            ],
        },
        servicelevels={"properties": [{"property": "freshness", "value": 24, "unit": "h"}]},
    )
    assert m.models.model_dump()["quality"][0]["metric"] == "nullValues"
    assert m.servicelevels.model_dump() == {
        "properties": [{"property": "freshness", "value": 24, "unit": "h"}]
    }


def test_unrunnable_rule_is_rejected_with_its_reason():
    with pytest.raises(ValidationError, match="percent"):
        ModelsSection(
            fields=[{"name": "id", "type": "integer"}],
            quality=[library_rule(metric="duplicateValues", column="id", unit="percent")],
        )


def test_service_levels_forbid_unknown_keys():
    with pytest.raises(ValidationError):
        ServiceLevels.model_validate({"properties": [], "freshness": "24h"})


def test_blank_service_level_value_is_rejected():
    with pytest.raises(ValidationError):
        ServiceLevels.model_validate({"properties": [{"property": "freshness", "value": " "}]})


def test_old_service_level_shape_is_rejected():
    with pytest.raises(ValidationError):
        DataContractCreateModel(
            title="x", owner="o", domain_id=DOMAIN_ID, tier=2,
            servicelevels={"freshness": "24h", "availability": "", "retention": "", "latency": ""},
        )


def test_old_rule_shape_is_rejected():
    with pytest.raises(ValidationError):
        ModelsSection(quality=[{"dimension": "completeness", "column": "", "operator": ">=",
                                "threshold": "99%"}])


def test_schema_literals_match_the_domain_values():
    from typing import get_args

    from backend.domain.contract_values import CONTRACT_STATUSES, FIELD_TYPES
    from backend.domain.quality_rules import (
        QUALITY_DIMENSIONS,
        QUALITY_METRICS,
        QUALITY_OPERATORS,
        QUALITY_UNITS,
    )
    from backend.interface.schemas.data_contract import (
        DataContractUpdateModel,
        QualityRule,
        SchemaField,
    )

    def literal(model, name):
        args = get_args(model.model_fields[name].annotation)
        # `Literal[...] | None` nests the Literal one level down.
        return tuple(a for arg in args for a in (get_args(arg) or (arg,)) if a is not type(None))

    # A contract is not born retired: creation takes every status but the last.
    assert literal(DataContractCreateModel, "status") == CONTRACT_STATUSES[:-1]
    assert literal(DataContractUpdateModel, "status") == CONTRACT_STATUSES
    assert literal(SchemaField, "type") == FIELD_TYPES
    assert literal(QualityRule, "dimension") == QUALITY_DIMENSIONS
    assert literal(QualityRule, "metric") == QUALITY_METRICS
    assert literal(QualityRule, "operator") == QUALITY_OPERATORS
    assert literal(QualityRule, "unit") == QUALITY_UNITS
