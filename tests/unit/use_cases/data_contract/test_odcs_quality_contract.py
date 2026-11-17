import json
from pathlib import Path

import jsonschema
import pytest

from backend.use_cases.data_contract.odcs import OdcsParseError, from_odcs, to_odcs
from tests.quality_rule_builders import orders_contract

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

def test_old_shape_still_emits_until_contraction():  # deleted in Task 9
    old = orders_contract()
    old.models = {**old.models, "quality": [{"dimension": "completeness", "column": "customer_id",
                  "operator": ">=", "threshold": "99%", "description": ""}]}
    old.servicelevels = {"freshness": "24h", "availability": "", "retention": "", "latency": ""}
    assert list(VALIDATOR.iter_errors(to_odcs(old))) == []
