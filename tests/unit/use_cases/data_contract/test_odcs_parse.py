import itertools

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
    sample_contract,
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
    itertools.product(["draft", "in_review", "active", "deprecated", "retired"], [1, 2, 3, 4]),
)
def test_round_trip_status_and_tier(status, tier):
    _assert_round_trip(make_contract(status=status, tier=tier))


@pytest.mark.parametrize(
    ("field_type", "nullable", "primary_key"),
    itertools.product(
        ["string", "integer", "float", "boolean", "date", "timestamp"],
        [True, False],
        [True, False],
    ),
)
def test_round_trip_field(field_type, nullable, primary_key):
    field = make_field("a", field_type, "text", nullable, primary_key)
    _assert_round_trip(make_contract(models={"fields": [field], "quality": []}))


def test_missing_tier_means_4():
    doc = _doc()
    del doc["customProperties"]
    assert from_odcs(doc).tier == 4


def test_missing_domain_is_empty_for_the_sync_to_report():
    doc = _doc()
    del doc["domain"]
    assert from_odcs(doc).domain_name == ""


def test_version_read_as_a_number_is_kept_as_text():
    assert from_odcs(_doc(version=1.0)).version == "1.0"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"apiVersion": "v2.2.2"}, "apiVersion 'v2.2.2'"),
        ({"kind": "DataProduct"}, "kind 'DataProduct'"),
        ({"schema": [{"name": "a"}, {"name": "b"}]}, "2 schema objects"),
        ({"status": "bogus"}, "status 'bogus'"),
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
        ({"slaProperties": [{"value": 1}]}, "malformed"),
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
