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
    make_rule,
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


# Every dimension, operator and column kind once; descriptions empty and written.
@pytest.mark.parametrize(
    ("dimension", "column", "operator", "description"),
    [("completeness", "", ">=", ""), ("freshness", "a", "<=", "free text"),
     ("uniqueness", "ghost", "=", ""), ("validity", "a", ">=", "free text"),
     ("integrity", "ghost", "<=", "")],
)
def test_round_trip_rule(dimension, column, operator, description):
    rule = make_rule(dimension, column, operator, "0.99", description)
    models = {"fields": [make_field("a")], "quality": [rule]}
    _assert_round_trip(make_contract(models=models))


@pytest.mark.parametrize("order", [["z", "a", "", "ghost"], ["ghost", "", "a", "z"]])
def test_round_trip_keeps_rule_order(order):
    models = {"fields": [make_field("z"), make_field("a")],
              "quality": [make_rule(column=column) for column in order]}
    _assert_round_trip(make_contract(models=models))


@pytest.mark.parametrize("raw", [raw for raw, _ in SLA_CASES])
def test_round_trip_sla_value(raw):
    levels = {"freshness": raw, "availability": "", "retention": "", "latency": ""}
    _assert_round_trip(make_contract(servicelevels=levels))


def test_sla_unit_aliases_are_read():
    doc = _doc(slaProperties=[{"property": "availability", "value": 99, "unit": "percent"},
                              {"property": "latency", "value": 30, "unit": "m"}])
    levels = from_odcs(doc).servicelevels
    assert (levels["availability"], levels["latency"]) == ("99%", "30m")


def test_threshold_edited_in_git_is_read_with_no_stale_description():
    doc = to_odcs(make_contract(models={"fields": [], "quality": [make_rule()]}))
    custom = doc["schema"][0]["quality"][0]["customProperties"]
    next(e for e in custom if e["property"] == "dmpltThreshold")["value"] = "95"
    rule = from_odcs(doc).models["quality"][0]
    assert (rule["threshold"], rule["description"]) == ("95", "")


def test_sla_key_outside_the_four_is_kept():
    doc = _doc(slaProperties=[{"property": "endOfSupport", "value": "2030-01-01"}])
    assert from_odcs(doc).servicelevels == {
        "freshness": "", "availability": "", "retention": "", "latency": "",
        "endOfSupport": "2030-01-01",
    }


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
        ({"slaProperties": [{"property": "a", "value": True}]}, "no storable value"),
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


@pytest.mark.parametrize(
    "rule",
    [{"type": "library", "metric": "nullValues", "mustBe": 0},
     {"type": "text", "description": "Hand written"},
     {"type": "sql", "customProperties": [
         {"property": "dmpltDimension", "value": "freshness"},
         {"property": "dmpltOperator", "value": "<="},
         {"property": "dmpltThreshold", "value": "24h"},
         {"property": "dmpltPosition", "value": 0}]}],
    ids=["library", "text-without-dmplt", "non-text-with-dmplt"],
)
def test_rule_outside_the_stored_format_is_rejected(rule):
    with pytest.raises(OdcsParseError, match="quality rule on the schema"):
        from_odcs(_doc(schema=[{"name": "a", "quality": [rule]}]))


def _with_property(**values) -> dict:
    prop = {"name": "b", "logicalType": "string", **values}
    return _doc(schema=[{"name": "a", "properties": [prop]}])


@pytest.mark.parametrize(("values", "message"), [
    ({"required": "false"}, "required must be of type bool"),
    ({"primaryKey": None}, "primaryKey must be of type bool"),
    ({"description": 5}, "description must be of type str"),
    ({"name": None}, "needs a non-empty name"),
    ({"name": " "}, "needs a non-empty name"),
])
def test_property_values_must_have_the_stored_type(values, message):
    with pytest.raises(OdcsParseError, match=message):
        from_odcs(_with_property(**values))


PLAN1_CUSTOM = {"dmpltDimension": "freshness", "dmpltOperator": "<=",
                "dmpltThreshold": "24h", "dmpltPosition": 0}


def _with_rule(custom=None, **values) -> dict:
    entries = {**PLAN1_CUSTOM, **(custom or {})}
    rule = {"type": "text", **values,
            "customProperties": [{"property": k, "value": v} for k, v in entries.items()]}
    return _doc(schema=[{"name": "a", "quality": [rule]}])


@pytest.mark.parametrize(("custom", "values", "message"), [
    ({"dmpltOperator": "!="}, {}, "dmpltOperator '!='"),
    ({"dmpltDimension": "accuracy"}, {}, "dmpltDimension 'accuracy'"),
    ({}, {"dimension": "accuracy"}, "dimension does not match dmpltDimension"),
    ({"dmpltThreshold": 99}, {}, "dmpltThreshold must be of type str"),
    ({"dmpltPosition": True}, {}, "dmpltPosition must be of type int"),
    ({"dmpltColumn": 3}, {}, "column must be of type str"),
    ({}, {"description": 5}, "description must be of type str"),
])
def test_rule_values_the_api_would_refuse_are_rejected(custom, values, message):
    with pytest.raises(OdcsParseError, match=message):
        from_odcs(_with_rule(custom, **values))


@pytest.mark.parametrize(("key", "value"), [("logicalType", "array"),
                                            ("physicalType", "view")])
def test_schema_object_edits_the_model_would_drop_are_rejected(key, value):
    with pytest.raises(OdcsParseError, match=f"schema {key} must be"):
        from_odcs(_doc(schema=[{"name": "a", key: value}]))
