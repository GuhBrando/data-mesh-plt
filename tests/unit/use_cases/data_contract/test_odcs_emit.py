import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from backend.use_cases.data_contract.odcs import to_odcs
from backend.use_cases.data_contract.yaml_builder import assemble_yaml
from tests.quality_rule_builders import text_rule
from tests.fixtures.odcs.sample_contract import (
    emit,
    make_contract,
    make_field,
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
    - type: library
      dimension: completeness
      metric: nullValues
      mustBeLessOrEqualTo: 0.5
      unit: percent
      description: Every order has an id
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
    description: Orders arrive within 24 hours.
  - type: library
    dimension: completeness
    metric: rowCount
    mustBeGreaterThan: 0
    unit: rows
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


def test_representative_contract_maps_to_expected_document():
    assert to_odcs(sample_contract()) == yaml.safe_load(EXPECTED_YAML)


@pytest.mark.parametrize(
    "contract",
    [
        sample_contract(),
        make_contract(),
        make_contract(title="", owner=""),
        make_contract(models={"fields": [], "quality": [text_rule()]}),
        make_contract(models={"fields": [make_field()], "quality": []}),
    ],
    ids=["sample", "empty", "blank", "only-quality", "only-fields"],
)
def test_output_is_valid_against_the_official_schema(contract):
    assert list(VALIDATOR.iter_errors(emit(contract))) == []


def test_schema_validator_rejects_a_legacy_document():
    assert list(VALIDATOR.iter_errors({"dataContractSpecification": "0.9.3"}))


@pytest.mark.parametrize(
    ("status", "expected"),
    [("draft", "draft"), ("in_review", "proposed"), ("active", "active"),
     ("deprecated", "deprecated"), ("retired", "retired")],
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


def test_empty_sla_values_are_omitted():
    assert "slaProperties" not in to_odcs(make_contract())


def test_assemble_yaml_emits_the_expected_text():
    assert assemble_yaml(sample_contract()) == EXPECTED_YAML
