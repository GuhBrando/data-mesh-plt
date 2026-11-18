import pytest

from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.odcs import (
    OdcsParseError,
    ParsedContract,
    from_odcs,
    to_odcs,
)
from tests.fixtures.odcs.sample_contract import (
    emit,
    make_contract,
    make_field,
    sample_contract,
    SLA_CASES,
)


def _assert_round_trip(c: DataContract) -> None:
    assert from_odcs(emit(c)) == ParsedContract(
        id=c.id, title=c.title, version=c.version, owner=c.owner, domain_name=c.domain,
        tier=c.tier, status=c.status, models=c.models, servicelevels=c.servicelevels,
    )


def _doc(**overrides) -> dict:
    return {**to_odcs(sample_contract()), **overrides}


def test_round_trip_representative_contract():
    _assert_round_trip(sample_contract())


@pytest.mark.parametrize(
    ("status", "tier"),
    zip(["draft", "in_review", "active", "deprecated"], [1, 2, 3, 4], strict=True),
)
def test_round_trip_status_and_tier(status, tier):
    _assert_round_trip(make_contract(status=status, tier=tier))


@pytest.mark.parametrize(
    ("field_type", "nullable", "primary_key"),
    [("string", True, True), ("integer", False, False), ("float", True, False),
     ("boolean", False, True), ("date", True, True), ("timestamp", False, False)],
)
def test_round_trip_field(field_type, nullable, primary_key):
    field = make_field("a", field_type, "text", nullable, primary_key)
    _assert_round_trip(make_contract(models={"fields": [field], "quality": []}))


def test_missing_tier_means_4():
    doc = _doc()
    del doc["customProperties"]
    assert from_odcs(doc).tier == 4


def test_missing_domain_is_empty_for_the_sync_to_report():
    doc = _doc()
    del doc["domain"]
    assert from_odcs(doc).domain_name == ""


def test_missing_team_means_no_owner():
    doc = _doc()
    del doc["team"]
    assert from_odcs(doc).owner == ""


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"apiVersion": "v2.2.2"}, "apiVersion 'v2.2.2'"),
        ({"kind": "DataProduct"}, "kind 'DataProduct'"),
        ({"schema": [{"name": "a"}, {"name": "b"}]}, "2 schema objects"),
        ({"status": "retired"}, "status 'retired'"),
        ({"id": "not-a-uuid"}, "not a UUID"),
        ({"team": [{"username": "a"}]}, "deprecated array"),
        ({"tags": []}, "unsupported keys: tags"),
        ({"team": {"name": "a", "tags": []}}, "team has unsupported keys: tags"),
        ({"customProperties": [{"property": "cost", "value": 1}]},
         "customProperties has unsupported keys: cost"),
        ({"customProperties": [{"property": "tier", "value": 9}]}, "tier must be"),
        ({"customProperties": [{"property": "tier", "value": "2"}]}, "tier must be"),
        ({"slaProperties": [{"property": "a", "value": 1, "driver": "x"}]}, "driver"),
        ({"slaProperties": [{"property": "a", "value": None}]}, "no storable value"),
        ({"slaProperties": [{"value": 1}]}, "malformed"),
        # An unquoted 1.10 loads as the float 1.1; null as None.
        ({"version": 1.1}, "version must be of type str"),
        ({"version": None}, "version must be of type str"),
        ({"name": 7}, "name must be of type str"),
        ({"customProperties": [{"property": "tier", "value": 2},
                               {"property": "tier", "value": 3}]}, "more than once"),
        ({"customProperties": [{"property": "tier", "value": 2, "id": "x"}]},
         "entry tier has unsupported keys: id"),
        ({"slaProperties": [{"property": "a", "value": 1},
                            {"property": "a", "value": 2}]}, "more than once"),
        ({"bad\nkey": 1}, r"unsupported keys: bad\\nkey"),
        ({f"k{i:02}": 1 for i in range(15)}, "and 5 more"),
    ],
)
def test_parse_errors(overrides, message):
    with pytest.raises(OdcsParseError, match=message):
        from_odcs(_doc(**overrides))


@pytest.mark.parametrize(
    "logical", ["time", "object", "array", "map", "vector", None]
)
def test_logical_type_the_model_cannot_hold(logical):
    prop = {"name": "b", "logicalType": logical}
    with pytest.raises(OdcsParseError, match=f"logicalType {logical!r}"):
        from_odcs(_doc(schema=[{"name": "a", "properties": [prop]}]))


def _with_property(**values) -> dict:
    prop = {"name": "b", "logicalType": "string", **values}
    return _doc(schema=[{"name": "a", "properties": [prop]}])


@pytest.mark.parametrize(("values", "message"), [
    ({"required": "false"}, "required must be of type bool"),
    ({"primaryKey": None}, "primaryKey must be of type bool"),
    ({"unique": "yes"}, "unique must be of type bool"),
    ({"physicalType": 5}, "physicalType must be of type str"),
    ({"description": 5}, "description must be of type str"),
    ({"name": None}, "needs a non-empty name"),
    ({"name": " "}, "needs a non-empty name"),
])
def test_property_values_must_have_the_stored_type(values, message):
    with pytest.raises(OdcsParseError, match=message):
        from_odcs(_with_property(**values))


@pytest.mark.parametrize(("key", "value"), [("logicalType", "array"),
                                            ("physicalType", "view")])
def test_schema_object_edits_the_model_would_drop_are_rejected(key, value):
    with pytest.raises(OdcsParseError, match=f"schema {key} must be"):
        from_odcs(_doc(schema=[{"name": "a", key: value}]))
