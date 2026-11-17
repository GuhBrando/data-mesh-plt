import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from backend.use_cases.data_contract.odcs import to_odcs
from backend.use_cases.data_contract.yaml_builder import assemble_yaml
from tests.fixtures.odcs.sample_contract import (
    emit,
    make_contract,
    make_field,
    make_rule,
    sample_contract,
)

SCHEMA = Path(__file__).parents[3] / "fixtures/odcs/odcs-json-schema-v3.2.0.json"
VALIDATOR = jsonschema.Draft201909Validator(
    json.loads(SCHEMA.read_text(encoding="utf-8"))
)

EXPECTED_YAML = """\
apiVersion: v3.2.0
kind: DataContract
id: 3f2a1c9e-8b7d-4e6f-a5c4-1d2e3f4a5b6c
name: Customer Orders
version: 1.2.0
status: proposed
domain: commerce
team:
  name: sales-team
schema:
- name: customer_orders
  logicalType: object
  physicalType: table
  properties:
  - name: order_id
    description: Order identifier
    logicalType: string
    required: true
    primaryKey: true
    quality:
    - type: text
      dimension: completeness
      description: Every order has an id
      customProperties:
      - property: dmpltDimension
        value: completeness
      - property: dmpltOperator
        value: '>='
      - property: dmpltThreshold
        value: '99.5'
      - property: dmpltPosition
        value: 1
  - name: amount
    description: Order total in BRL
    logicalType: number
    required: false
    primaryKey: false
  - name: created_at
    description: ''
    logicalType: timestamp
    required: true
    primaryKey: false
  quality:
  - type: text
    dimension: timeliness
    description: Freshness of the table must be <= 24h.
    customProperties:
    - property: dmpltDimension
      value: freshness
    - property: dmpltOperator
      value: <=
    - property: dmpltThreshold
      value: 24h
    - property: dmpltPosition
      value: 0
  - type: text
    dimension: conformity
    description: Only BRL orders
    customProperties:
    - property: dmpltDimension
      value: validity
    - property: dmpltOperator
      value: '='
    - property: dmpltThreshold
      value: BRL
    - property: dmpltColumn
      value: currency
    - property: dmpltPosition
      value: 2
slaProperties:
- property: freshness
  value: 24
  unit: h
- property: availability
  value: 99.9
  unit: '%'
- property: retention
  value: one year
customProperties:
- property: tier
  value: 2
"""


def _custom(rule: dict) -> dict:
    return {entry["property"]: entry["value"] for entry in rule["customProperties"]}


def test_representative_contract_maps_to_expected_document():
    assert to_odcs(sample_contract()) == yaml.safe_load(EXPECTED_YAML)


@pytest.mark.parametrize(
    "contract",
    [
        sample_contract(),
        make_contract(),
        make_contract(title="", owner=""),
        make_contract(models={"fields": [], "quality": [make_rule(column="ghost")]}),
        make_contract(models={"fields": [make_field()], "quality": []}),
        make_contract(models={"quality": [{"dimension": "not-in-the-model"}]}),
    ],
    ids=["sample", "empty", "blank", "only-quality", "only-fields", "partial-rule"],
)
def test_output_is_valid_against_the_official_schema(contract):
    assert list(VALIDATOR.iter_errors(emit(contract))) == []


def test_schema_validator_rejects_a_legacy_document():
    assert list(VALIDATOR.iter_errors({"dataContractSpecification": "0.9.3"}))


@pytest.mark.parametrize(
    ("status", "expected"),
    [("draft", "draft"), ("in_review", "proposed"), ("active", "active"),
     ("deprecated", "deprecated")],
)
def test_status_mapping(status, expected):
    assert to_odcs(make_contract(status=status))["status"] == expected


def test_field_mapping():
    field = make_field("a", "float", "text", nullable=False, primary_key=True)
    doc = to_odcs(make_contract(models={"fields": [field], "quality": []}))
    assert doc["schema"][0]["properties"] == [
        {"name": "a", "description": "text", "logicalType": "number",
         "required": True, "primaryKey": True}
    ]


def test_schema_omitted_without_fields_and_quality():
    assert "schema" not in to_odcs(make_contract())


@pytest.mark.parametrize(
    ("title", "expected"),
    [("Customer Orders", "customer_orders"),
     ("Pedidos de Exportação", "pedidos_de_exportacao"),
     ("  --- ", "contract"), ("", "contract")],
)
def test_schema_name_is_a_snake_case_slug(title, expected):
    models = {"fields": [make_field()], "quality": []}
    doc = to_odcs(make_contract(title=title, models=models))
    assert doc["schema"][0]["name"] == expected


@pytest.mark.parametrize(
    ("field", "column", "under_property", "dmplt_column"),
    [("id", "id", True, None), ("id", "ghost", False, "ghost"),
     ("id", "", False, None), ("", "", False, None)],
)
def test_rule_placement(field, column, under_property, dmplt_column):
    models = {"fields": [make_field(field)], "quality": [make_rule(column=column)]}
    schema = to_odcs(make_contract(models=models))["schema"][0]
    prop = schema["properties"][0]
    owner, other = (prop, schema) if under_property else (schema, prop)
    assert "quality" not in other
    assert owner["quality"][0]["type"] == "text"
    assert _custom(owner["quality"][0]).get("dmpltColumn") == dmplt_column


@pytest.mark.parametrize(
    ("dimension", "expected"),
    [("completeness", "completeness"), ("uniqueness", "uniqueness"),
     ("freshness", "timeliness"), ("validity", "conformity"),
     ("integrity", "consistency")],
)
def test_dimension_mapping_keeps_the_original_value(dimension, expected):
    models = {"fields": [], "quality": [make_rule(dimension=dimension)]}
    rule = to_odcs(make_contract(models=models))["schema"][0]["quality"][0]
    assert rule["dimension"] == expected
    assert _custom(rule)["dmpltDimension"] == dimension


def test_rule_without_description_gets_a_sentence():
    models = {"fields": [], "quality": [make_rule("freshness", "", "<=", "24h"),
                                        make_rule("validity", "ghost", "=", "BRL")]}
    rules = to_odcs(make_contract(models=models))["schema"][0]["quality"]
    assert rules[0]["description"] == "Freshness of the table must be <= 24h."
    assert rules[1]["description"] == "Validity of column ghost must be = BRL."


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("24h", {"value": 24, "unit": "h"}),
     ("99.9%", {"value": 99.9, "unit": "%"}),
     ("365d", {"value": 365, "unit": "d"}),
     ("100.0%", {"value": 100.0, "unit": "%"}),
     ("30m", {"value": 30, "unit": "min"}),
     ("24", {"value": 24})],
)
def test_sla_value_is_split(raw, expected):
    doc = to_odcs(make_contract(servicelevels={"freshness": raw}))
    assert doc["slaProperties"] == [{"property": "freshness", **expected}]


@pytest.mark.parametrize(
    "raw", ["hourly", "24 h", "1.50h", "007", "5percent", "30min", "24h\n", "٣h"]
)
def test_sla_value_that_cannot_be_rebuilt_stays_a_string(raw):
    doc = to_odcs(make_contract(servicelevels={"freshness": raw}))
    assert doc["slaProperties"] == [{"property": "freshness", "value": raw}]


def test_empty_sla_values_are_omitted():
    assert "slaProperties" not in to_odcs(make_contract())


def test_assemble_yaml_emits_the_expected_text():
    assert assemble_yaml(sample_contract()) == EXPECTED_YAML
