import uuid

import pytest
import yaml

from backend.use_cases.data_contract.contract_document import parse_contract_document
from backend.use_cases.data_contract.legacy_dcs import from_legacy_dcs
from backend.use_cases.data_contract.odcs import OdcsParseError, to_odcs
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
    assert parsed.servicelevels == {"freshness": "24h", "availability": "99%",
                                    "retention": "365d", "latency": "1h"}


def test_legacy_defaults_match_the_previous_sync():
    parsed = from_legacy_dcs({"id": str(uuid.uuid4()), "servicelevels": None})
    assert (parsed.title, parsed.version, parsed.owner) == ("", "1.0.0", "")
    assert (parsed.domain_name, parsed.tier, parsed.status) == ("", 4, "draft")
    assert parsed.models == {}
    assert parsed.servicelevels == {}


def test_legacy_quality_is_merged_into_models():
    doc = yaml.safe_load(LEGACY_FILE)
    doc["quality"] = [{"dimension": "freshness"}]
    assert from_legacy_dcs(doc).models == {
        "fields": [], "quality": [{"dimension": "freshness"}],
    }


def test_marker_routes_to_the_legacy_reader():
    assert parse_contract_document(yaml.safe_load(LEGACY_FILE)).title == "Sales"


def test_no_marker_routes_to_the_odcs_reader():
    parsed = parse_contract_document(to_odcs(sample_contract()))
    assert parsed.title == "Customer Orders"


def test_document_with_neither_format_is_an_odcs_error():
    with pytest.raises(OdcsParseError, match="apiVersion"):
        parse_contract_document({"id": str(uuid.uuid4()), "info": {}})


@pytest.mark.parametrize("doc", [None, [], "text"])
def test_non_mapping_document_is_rejected(doc):
    with pytest.raises(OdcsParseError, match="not a YAML mapping"):
        parse_contract_document(doc)
