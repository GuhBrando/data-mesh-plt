import uuid

import pytest
import yaml

from backend.use_cases.data_contract.contract_document import (
    MAX_CONTRACT_CHARS,
    load_contract_yaml,
    parse_contract_document,
)
from backend.use_cases.data_contract.legacy_dcs import from_legacy_dcs
from backend.use_cases.data_contract.odcs import OdcsParseError, to_odcs
from backend.use_cases.data_contract.parsed_contract import ContractParseError
from tests.fixtures.odcs.sample_contract import sample_contract

# contracts/commerce/sales.yaml in GuhBrando/dmplt_data_contract
LEGACY_FILE = """\
dataContractSpecification: 0.9.3
id: 87e003b4-88c3-43b3-9819-d06d592dbb58
info:
  title: Sales
  version: 1.0.0
  owner: alice
  domain: commerce
  status: draft
models:
  fields: []
servicelevels:
  freshness: 24h
  availability: 99%
  retention: 365d
  latency: 1h
x-tier: 2
"""


def test_legacy_file_is_read_with_its_stored_shape():
    parsed = from_legacy_dcs(yaml.safe_load(LEGACY_FILE))
    assert parsed.id == uuid.UUID("87e003b4-88c3-43b3-9819-d06d592dbb58")
    assert (parsed.title, parsed.version, parsed.owner) == ("Sales", "1.0.0", "alice")
    assert (parsed.domain_name, parsed.tier, parsed.status) == ("commerce", 2, "draft")
    assert parsed.models == {"fields": []}
    assert parsed.servicelevels == {"properties": [
        {"property": "freshness", "value": 24, "unit": "h"},
        {"property": "availability", "value": 99, "unit": "%"},
        {"property": "retention", "value": 365, "unit": "d"},
        {"property": "latency", "value": 1, "unit": "h"},
    ]}


def test_legacy_defaults_match_the_previous_sync():
    parsed = from_legacy_dcs({"id": str(uuid.uuid4()), "servicelevels": None})
    assert (parsed.title, parsed.version, parsed.owner) == ("", "1.0.0", "")
    assert (parsed.domain_name, parsed.tier, parsed.status) == ("", 4, "draft")
    assert parsed.models == {}
    assert parsed.servicelevels == {"properties": []}


def test_legacy_quality_is_merged_into_models():
    doc = yaml.safe_load(LEGACY_FILE)
    doc["quality"] = [{"dimension": "freshness"}]
    assert from_legacy_dcs(doc).models == {
        "fields": [],
        "quality": [{
            "type": "text", "dimension": "timeliness", "column": "", "metric": None,
            "operator": None, "value": None, "unit": None, "valid_values": [],
            "description": "[legacy rule: dimension=freshness column= operator= threshold=]",
        }],
    }


def test_legacy_service_levels_keep_text_and_minutes():
    doc = yaml.safe_load(LEGACY_FILE)
    doc["servicelevels"] = {"freshness": "30m", "availability": "best effort",
                            "retention": "", "latency": None}
    assert from_legacy_dcs(doc).servicelevels == {"properties": [
        {"property": "freshness", "value": 30, "unit": "min"},
        {"property": "availability", "value": "best effort", "unit": None},
    ]}


def test_legacy_rule_keeps_its_values_in_the_description():
    doc = yaml.safe_load(LEGACY_FILE)
    doc["models"] = {"fields": [{"name": "id", "type": "string"}]}
    doc["quality"] = [
        {"dimension": "completeness", "column": "id", "operator": ">=",
         "threshold": "99%", "description": "Ids are present"},
        {"dimension": "validity", "column": "ghost", "operator": "=", "threshold": "BRL"},
    ]
    rules = from_legacy_dcs(doc).models["quality"]
    assert [(r["type"], r["dimension"], r["column"]) for r in rules] == [
        ("text", "completeness", "id"), ("text", "conformity", ""),
    ]
    assert rules[0]["description"] == (
        "Ids are present [legacy rule: dimension=completeness column=id"
        " operator=>= threshold=99%]"
    )
    assert "column=ghost" in rules[1]["description"]


def test_marker_routes_to_the_legacy_reader():
    assert parse_contract_document(yaml.safe_load(LEGACY_FILE)).title == "Sales"


def test_no_marker_routes_to_the_odcs_reader():
    parsed = parse_contract_document(to_odcs(sample_contract()))
    assert parsed.title == "Customer Orders"


def test_document_with_neither_format_is_an_odcs_error():
    with pytest.raises(OdcsParseError, match="apiVersion"):
        parse_contract_document({"id": str(uuid.uuid4()), "name": "x"})


def test_legacy_file_without_the_marker_is_still_read():
    # The sync before ODCS read any mapping through `info`.
    doc = yaml.safe_load(LEGACY_FILE)
    del doc["dataContractSpecification"]
    assert parse_contract_document(doc).title == "Sales"


@pytest.mark.parametrize("doc", [None, [], "text"])
def test_non_mapping_document_is_rejected(doc):
    with pytest.raises(ContractParseError, match="not a YAML mapping"):
        parse_contract_document(doc)


@pytest.mark.parametrize(("models", "quality", "message"), [
    ({"fields": {"id": {"type": "string"}}}, None, "models.fields must be a list"),
    ({"fields": ["id"]}, None, "models.fields must be a list"),
    ("fields", None, "models must be an object"),
    ({"fields": []}, "a rule", "quality must be a list"),
])
def test_legacy_models_the_platform_cannot_write_back_are_rejected(models, quality, message):
    doc = yaml.safe_load(LEGACY_FILE)
    doc["models"] = models
    if quality is not None:
        doc["quality"] = quality
    with pytest.raises(ContractParseError, match=message):
        from_legacy_dcs(doc)


def test_yaml_aliases_are_refused():
    bomb = "\n".join(['a: &a ["x", "x"]', "b: &b [*a, *a]", "c: [*b, *b]"])
    with pytest.raises(ContractParseError, match="aliases"):
        load_contract_yaml(bomb)


def test_oversized_file_is_refused_before_parsing():
    with pytest.raises(ContractParseError, match="larger than"):
        load_contract_yaml("x" * (MAX_CONTRACT_CHARS + 1))


def test_plain_yaml_loads():
    assert load_contract_yaml(LEGACY_FILE)["info"]["title"] == "Sales"


def test_legacy_rules_inside_models_are_converted_too():
    # Stored raw, they would crash to_odcs, which emits only the new rule shape.
    doc = yaml.safe_load(LEGACY_FILE)
    doc["models"] = {"fields": [], "quality": [
        {"dimension": "freshness", "operator": "<=", "threshold": "24h"}]}
    [rule] = from_legacy_dcs(doc).models["quality"]
    assert (rule["type"], rule["dimension"]) == ("text", "timeliness")
