"""The ODPS v1.1.0 export, checked against the official JSON Schema."""

import hashlib
import uuid

import pytest

from backend.use_cases.data_product.odps import ODPS_API_VERSION, to_odps
from tests.fixtures.odps.sample_product import (
    CADASTRO,
    EXPOSICAO,
    PRODUCT_ID,
    full_product,
    make_product,
)
from tests.fixtures.odps.validator import SCHEMA_FILE, problems

V1_1_0_SHA256 = "b7eae1af15b3c6b18e5dffaa2119212acb38ec73286933c76d16c8712e0d90d1"


def test_vendored_schema_is_the_v1_1_0_tag():
    # The upstream file, byte for byte, except for line endings on checkout and
    # the final newline the end-of-file hook adds.
    content = SCHEMA_FILE.read_bytes().replace(b"\r\n", b"\n").removesuffix(b"\n")
    assert hashlib.sha256(content).hexdigest() == V1_1_0_SHA256


def test_minimal_product_validates():
    doc = to_odps(make_product())
    assert doc == {
        "apiVersion": "v1.1.0",
        "kind": "DataProduct",
        "id": str(PRODUCT_ID),
        "name": "Risco de Crédito",
        "status": "active",
        "domain": "Risco",
        "outputPorts": [{"name": "exposicao", "id": str(uuid.UUID(int=1))}],
        "productCreatedTs": "2026-11-24T13:30:00Z",
    }
    assert problems(doc) == []


def test_full_product_validates():
    assert problems(to_odps(full_product())) == []


def test_api_version_is_v1_1_0():
    assert ODPS_API_VERSION == "v1.1.0"


def test_keys_are_odps_camel_case():
    doc = to_odps(full_product())
    assert doc["team"]["members"][0]["dateIn"] == "2026-01-01"
    assert doc["team"]["members"][1]["replacedByUsername"] == "ana"
    assert doc["support"][0]["invitationUrl"] == "https://join"
    assert doc["context"]["verifiedStatements"] == [{"question": "Total exposure?", "answer": "sum(amount)"}]
    assert doc["description"]["customProperties"] == [{"property": "audience", "value": "risk"}]
    [exposicao, alerta] = doc["outputPorts"]
    assert exposicao["contractId"] == str(EXPOSICAO)
    assert exposicao["inputContracts"] == [{"id": str(CADASTRO), "version": "2.1.0"}]
    assert exposicao["sbom"] == [{"type": "external", "url": "https://sbom/exposicao"}]
    assert exposicao["customProperties"] == [{"property": "sla", "value": "daily"}]
    assert alerta == {"name": "alerta-limite", "type": "topic", "id": str(uuid.UUID(int=5))}
    assert doc["inputPorts"][0]["contractId"] == str(CADASTRO)
    assert doc["authoritativeDefinitions"] == [{"type": "businessDefinition", "url": "https://wiki/risco"}]
    assert [m["name"] for m in doc["managementPorts"]] == ["metrics", "alerts"]
    assert doc["managementPorts"][1] == {
        "name": "alerts", "content": "control", "type": "topic",
        "channel": "risco.alertas", "id": str(uuid.UUID(int=7)),
    }


def test_custom_property_values_are_left_alone():
    [cost_center, _] = to_odps(full_product())["customProperties"]
    assert cost_center == {"property": "cost_center", "value": {"area_code": 42, "nested_list": [1, 2]}}


@pytest.mark.parametrize("value", [0, False, "", [], {}])
def test_falsy_custom_property_values_are_kept(value):
    product = make_product(custom_properties=[{"property": "flag", "value": value}])
    assert to_odps(product)["customProperties"] == [{"property": "flag", "value": value}]


def test_variables_are_exported_verbatim():
    doc = to_odps(full_product())
    assert doc["version"] == "${PRODUCT_VERSION:-1.0.0}"
    assert doc["support"][0]["url"] == "${SUPPORT_URL}"
    assert doc["managementPorts"][0]["url"] == "${METRICS_URL}"


def test_platform_only_fields_are_not_exported():
    text = str(to_odps(full_product()))
    for leaked in ("repo_url", "github.com", "produced_by", "consumed_by", "warnings", "domain_id"):
        assert leaked not in text


@pytest.mark.parametrize("status, deprecated", [("active", None), ("deprecated", True), ("retired", True)])
def test_deprecated_follows_status(status, deprecated):
    assert to_odps(make_product(status=status)).get("deprecated") == deprecated


def test_port_deprecation_is_its_own():
    core = to_odps(full_product())["inputPorts"][1]
    assert core["deprecated"] is True
    assert "deprecated" not in to_odps(full_product())["inputPorts"][0]


def test_empty_sections_are_left_out():
    doc = to_odps(make_product())
    for section in ("description", "tags", "synonyms", "context", "team", "support",
                    "customProperties", "authoritativeDefinitions", "inputPorts",
                    "managementPorts", "version", "tenant", "type", "deprecated"):
        assert section not in doc, section


def test_prose_rules_hold():
    doc = to_odps(full_product())
    assert doc["outputPorts"]
    assert doc["status"] in ("proposed", "draft", "active", "deprecated", "retired")


def test_the_validator_reports_the_prose_rules():
    doc = to_odps(make_product()) | {"outputPorts": [], "status": "live"}
    assert problems(doc) == [
        "outputPorts: a data product needs at least one output port",
        "status: 'live' is not an ODPS status",
    ]
