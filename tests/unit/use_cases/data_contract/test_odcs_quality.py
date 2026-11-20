import json
from datetime import date, datetime, timezone

import pytest

from backend.domain.quality_rules import QUALITY_METRICS, QUALITY_OPERATORS
from backend.use_cases.data_contract.odcs_quality import (
    rule_from_odcs,
    rule_to_odcs,
    sla_from_odcs,
    sla_to_odcs,
)
from tests.fixtures.odcs.validator import VALIDATOR
from tests.quality_rule_builders import library_rule, text_rule


def _doc(property_rules=(), schema_rules=(), sla=()):  # minimal valid ODCS around the items
    doc = {"apiVersion": "v3.2.0", "kind": "DataContract", "id": "11111111-1111-4111-8111-111111111111",
           "name": "t", "version": "1.0.0", "status": "active",
           "schema": [{"name": "t", "logicalType": "object", "physicalType": "table",
                       "quality": list(schema_rules),
                       "properties": [{"name": "email", "logicalType": "string", "quality": list(property_rules)}]}]}
    if sla:
        doc["slaProperties"] = list(sla)
    return doc

def test_null_values_rule_is_valid_odcs():
    item = rule_to_odcs(library_rule(operator="mustBeLessOrEqualTo", value=1, unit="percent"))
    assert item == {"type": "library", "dimension": "completeness", "metric": "nullValues",
                    "mustBeLessOrEqualTo": 1, "unit": "percent"}
    assert list(VALIDATOR.iter_errors(_doc([item]))) == []

def test_invalid_values_carry_valid_values_as_arguments():
    item = rule_to_odcs(library_rule(metric="invalidValues", valid_values=["open", "paid"]))
    assert item["arguments"] == {"validValues": ["open", "paid"]}

def test_text_rule_has_no_metric_keys():
    assert rule_to_odcs(text_rule()) == {"type": "text", "dimension": "consistency",
                                         "description": "Totals reconcile with the ledger."}

# Each metric, operator and unit once: the mapper treats every one alike.
ROUND_TRIP = [
    library_rule(metric="nullValues", operator="mustBe", unit="percent"),
    library_rule(metric="missingValues", operator="mustNotBe", unit=None),
    library_rule(metric="invalidValues", operator="mustBeGreaterThan", valid_values=["a"]),
    library_rule(metric="duplicateValues", operator="mustBeGreaterOrEqualTo"),
    library_rule(metric="rowCount", column="", operator="mustBeLessThan"),
    library_rule(operator="mustBeLessOrEqualTo", dimension=None),
    text_rule(), text_rule(column="email", dimension=None),
]
assert {r["metric"] for r in ROUND_TRIP} >= set(QUALITY_METRICS)
assert {r["operator"] for r in ROUND_TRIP} >= set(QUALITY_OPERATORS)

@pytest.mark.parametrize("rule", ROUND_TRIP)
def test_rule_round_trip(rule):
    assert rule_from_odcs(rule_to_odcs(rule), rule["column"]) == rule

def test_type_defaults_follow_odcs():
    assert rule_from_odcs({"metric": "nullValues", "mustBe": 0}, "email")["type"] == "library"
    assert rule_from_odcs({"description": "x"}, "")["type"] == "text"

@pytest.mark.parametrize(("item", "fragment"), [
    ({"type": "sql", "query": "SELECT 1", "mustBe": 0}, "sql"),
    ({"type": "custom", "engine": "soda"}, "custom"),
    ({"metric": "rowCount", "mustBeBetween": [1, 2]}, "mustBeBetween"),
    ({"metric": "rowCount", "mustBeGreaterThan": 0, "mustBeLessThan": 9}, "exactly one operator"),
    ({"metric": "rowCount"}, "exactly one operator"),
    ({"metric": "invalidValues", "mustBe": 0, "arguments": {"pattern": "^a"}}, "pattern"),
    ({"metric": "missingValues", "mustBe": 0, "arguments": {"missingValues": ["N/A"]}}, "missingValues"),
    # from_odcs strips a Plan 1 text rule's dmplt* properties before calling this (Task 9).
    ({"type": "text", "description": "x",
      "customProperties": [{"property": "dmpltOperator", "value": ">="}]}, "customProperties"),
    ({"metric": "nullValues", "mustBe": 0, "severity": "error"}, "severity"),
    # A YAML scalar would otherwise split into one valid value per character.
    ({"metric": "invalidValues", "mustBe": 0, "arguments": {"validValues": "open"}}, "must be a list"),
    ({"metric": "invalidValues", "mustBe": 0, "arguments": "open"}, "must be an object"),
    ({"metric": "invalidValues", "mustBe": 0, "arguments": {"validValues": [None]}}, "scalar"),
    ({"metric": "invalidValues", "mustBe": 0, "arguments": {"validValues": [{"a": 1}]}}, "scalar"),
    ("not a rule", "must be an object"),
    ({"type": "text", "description": "x", "metric": "nullValues"}, "cannot carry metric"),
])
def test_rule_from_odcs_refuses_what_it_cannot_store(item, fragment):
    with pytest.raises(ValueError, match=fragment):
        rule_from_odcs(item, "email")

def test_sla_round_trip_is_valid_odcs():
    sl = {"properties": [{"property": "freshness", "value": 24, "unit": "h"},
                         {"property": "availability", "value": 99.9, "unit": "%"},
                         {"property": "retention", "value": "P1D", "unit": None}]}
    items = sla_to_odcs(sl)
    assert items[2] == {"property": "retention", "value": "P1D"}
    assert list(VALIDATOR.iter_errors(_doc(sla=items))) == []
    assert sla_from_odcs(items) == sl

def test_sla_from_odcs_normalises_units_and_scalars():
    parsed = sla_from_odcs([
        {"property": "availability", "value": 99, "unit": "percent"},
        {"property": "latency", "value": 30, "unit": "m"},
        {"property": "generalAvailability", "value": datetime(2022, 5, 12, 9, 30, tzinfo=timezone.utc)},
    ])
    assert [p["unit"] for p in parsed["properties"]] == ["%", "min", None]
    assert isinstance(parsed["properties"][2]["value"], str)
    json.dumps(parsed)

def test_sla_dates_are_stored_as_iso_text():
    [prop] = sla_from_odcs([{"property": "generalAvailability", "value": date(2022, 5, 12)}])["properties"]
    assert prop["value"] == "2022-05-12"


@pytest.mark.parametrize(("items", "fragment"), [
    ([{"property": "latency", "value": None}], "no storable value"),
    ([{"property": "latency", "value": {"a": 1}}], "no storable value"),
    ([{"property": "latency", "value": 4, "element": "t.c"}], "element"),
    (["latency"], "must be an object"),
    ({"property": "latency", "value": 4}, "must be a list"),
])
def test_sla_from_odcs_refuses_what_it_cannot_store(items, fragment):
    with pytest.raises(ValueError, match=fragment):
        sla_from_odcs(items)
