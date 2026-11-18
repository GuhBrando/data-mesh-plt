import json
from pathlib import Path

import jsonschema
import pytest

from backend.use_cases.data_contract.odcs import OdcsParseError, from_odcs, to_odcs
from tests.quality_rule_builders import orders_contract, text_rule

VALIDATOR = jsonschema.Draft201909Validator(
    json.loads(
        (Path(__file__).parents[3] / "fixtures/odcs/odcs-json-schema-v3.2.0.json").read_text(
            encoding="utf-8"
        )
    )
)


def test_emitted_contract_is_valid_odcs_without_custom_properties():
    doc = to_odcs(orders_contract())
    assert list(VALIDATOR.iter_errors(doc)) == []
    props = {p["name"]: p for p in doc["schema"][0]["properties"]}
    assert props["customer_id"]["quality"] == [{"type": "library", "dimension": "completeness",
        "metric": "nullValues", "mustBeLessOrEqualTo": 1, "unit": "percent"}]
    assert [q["metric"] for q in doc["schema"][0]["quality"] if q["type"] == "library"] == ["rowCount"]
    assert doc["slaProperties"][3] == {"property": "latency", "value": 30, "unit": "min"}
    assert "dmplt" not in json.dumps(doc)

def test_round_trip_returns_the_same_rules_and_service_levels():
    contract = orders_contract()
    parsed = from_odcs(to_odcs(contract))
    key = lambda r: json.dumps(r, sort_keys=True)
    assert sorted(parsed.models["quality"], key=key) == sorted(contract.models["quality"], key=key)
    assert parsed.servicelevels == contract.servicelevels

@pytest.mark.parametrize(("mutate", "fragment"), [
    (lambda d: d["schema"][0]["properties"][0]["quality"].append({"metric": "rowCount", "mustBeBetween": [1, 2]}), "mustBeBetween"),
    (lambda d: d["schema"][0]["quality"].append({"metric": "nullValues", "mustBe": 0}), "needs a column"),
    (lambda d: d["slaProperties"].append({"property": "latency", "value": 1, "unit": "h", "driver": "analytics"}), "driver"),
])
def test_from_odcs_refuses_what_the_platform_cannot_store(mutate, fragment):
    doc = to_odcs(orders_contract())
    mutate(doc)
    with pytest.raises(OdcsParseError, match=fragment):
        from_odcs(doc)


PLAN1_CUSTOM = [{"property": "dmpltDimension", "value": "completeness"},
                {"property": "dmpltOperator", "value": ">="},
                {"property": "dmpltThreshold", "value": "99"},
                {"property": "dmpltPosition", "value": 0}]

LEGACY = "[legacy rule: dimension=completeness column={} operator=>= threshold=99]"


def ON_CUSTOMER(d):  # customer_id
    return d["schema"][0]["properties"][1]


def ON_SCHEMA(d):
    return d["schema"][0]


@pytest.mark.parametrize(("place", "extra", "description", "column", "expected"), [
    (ON_CUSTOMER, [], "Kept as written", "customer_id",
     "Kept as written " + LEGACY.format("customer_id")),
    # Plan 1 no longer generates a sentence for an empty description, so the
    # file carries none and the text matches what the migration writes.
    (ON_CUSTOMER, [], "", "customer_id", LEGACY.format("customer_id")),
    (ON_SCHEMA, [{"property": "dmpltColumn", "value": "ghost"}], "Kept as written", "",
     "Kept as written " + LEGACY.format("ghost")),
], ids=["own-description", "no-description", "unknown-column"])
def test_plan1_text_rule_is_read_as_a_text_rule(place, extra, description, column, expected):
    doc = to_odcs(orders_contract())
    place(doc)["quality"] = [{"type": "text", "dimension": "completeness",
                              "description": description,
                              "customProperties": [*PLAN1_CUSTOM, *extra]}]
    rules = [r for r in from_odcs(doc).models["quality"] if "[legacy rule:" in r["description"]]
    assert rules == [text_rule(dimension="completeness", column=column, description=expected)]


@pytest.mark.parametrize("item", [
    {"type": "text", "description": "x", "customProperties": [{"property": "cost", "value": 1}]},
    {"type": "library", "metric": "rowCount", "mustBeGreaterThan": 0,
     "customProperties": PLAN1_CUSTOM},
])
def test_other_custom_properties_are_refused(item):
    doc = to_odcs(orders_contract())
    doc["schema"][0]["quality"].append(item)
    with pytest.raises(OdcsParseError, match="customProperties"):
        from_odcs(doc)
