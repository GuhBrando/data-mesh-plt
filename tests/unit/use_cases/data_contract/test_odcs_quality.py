import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

from backend.domain.quality_rules import (
    PERCENT_METRICS,
    QUALITY_METRICS,
    QUALITY_OPERATORS,
)
from backend.use_cases.data_contract.odcs_quality import (
    rule_from_odcs,
    rule_to_odcs,
    sla_from_odcs,
    sla_to_odcs,
)
from tests.quality_rule_builders import library_rule, text_rule


VALIDATOR = jsonschema.Draft201909Validator(json.loads(
    (Path(__file__).parents[3] / "fixtures/odcs/odcs-json-schema-v3.2.0.json").read_text(encoding="utf-8")))

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

ROUND_TRIP = [
    library_rule(metric=m, operator=op, unit=u, column="" if m == "rowCount" else "email",
                 valid_values=["a"] if m == "invalidValues" else [])
    for m in QUALITY_METRICS for op in QUALITY_OPERATORS
    for u in ("rows", None, *(("percent",) if m in PERCENT_METRICS else ()))
] + [text_rule(), text_rule(column="email", dimension=None)]

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

@pytest.mark.parametrize("item", [{"property": "latency", "value": None},
                                  {"property": "latency", "value": 4, "element": "t.c"}])
def test_sla_from_odcs_refuses_what_it_cannot_store(item):
    with pytest.raises(ValueError):
        sla_from_odcs([item])
