import json
from pathlib import Path

import jsonschema
import pytest

from backend.domain.contract_values import CLASSIFICATIONS
from backend.use_cases.data_contract.odcs import OdcsParseError, from_odcs, to_odcs
from tests.fixtures.odcs.sample_contract import (
    AZURE,
    DATABRICKS,
    FIELD,
    FULL_CONTRACT,
    make_contract,
)

SCHEMA = json.loads(Path("tests/fixtures/odcs/odcs-json-schema-v3.2.0.json").read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft201909Validator(SCHEMA)
SECRET = "not-a-real-secret"


def _contract(**kw):
    return make_contract(owner="commerce-data", **kw)


def _assert_valid(doc: dict) -> None:
    assert [e.message for e in VALIDATOR.iter_errors(doc)] == []


def _prop(doc: dict) -> dict:
    return doc["schema"][0]["properties"][0]


def test_full_contract_is_valid_and_round_trips():
    doc = to_odcs(FULL_CONTRACT)
    _assert_valid(doc)
    parsed = from_odcs(doc)
    for name in ("description", "team_members", "support", "servers"):
        assert getattr(parsed, name) == getattr(FULL_CONTRACT, name)
    assert parsed.models["fields"] == FULL_CONTRACT.models["fields"]


@pytest.mark.parametrize("kw, pick, expected", [
    (dict(description={"purpose": "p", "usage": "", "limitations": ""}), lambda d: d["description"],
     {"purpose": "p"}),
    (dict(team_members=[{"username": "a", "name": "", "role": "owner"}]), lambda d: d["team"],
     {"name": "commerce-data", "members": [{"username": "a", "role": "owner"}]}),
    (dict(support=[{"channel": "c", "url": "", "tool": "email", "scope": ""}]), lambda d: d["support"],
     [{"channel": "c", "tool": "email"}]),
    (dict(servers=[DATABRICKS]), lambda d: sorted(d["servers"][0]),
     ["catalog", "environment", "host", "schema", "server", "type"]),
    (dict(servers=[AZURE]), lambda d: d["servers"],
     [{"server": "lake", "type": "azure", "location": AZURE["location"], "format": "parquet"}]),
    (dict(models={"fields": [FIELD]}), lambda d: {k: _prop(d)[k] for k in ("classification", "unique", "physicalType")},
     {"classification": "internal", "unique": True, "physicalType": "VARCHAR(36)"}),
])
def test_emitted_shape(kw, pick, expected):
    assert pick(to_odcs(_contract(**kw))) == expected


def test_empty_sections_are_omitted_and_parse_to_defaults():
    doc = to_odcs(_contract())
    assert not {"description", "support", "servers"} & doc.keys() and "members" not in doc["team"]
    parsed = from_odcs(doc)
    assert parsed.description == {"purpose": "", "usage": "", "limitations": ""}
    assert (parsed.team_members, parsed.support, parsed.servers) == ([], [], [])


def test_field_stored_before_this_plan_still_emits():
    legacy = {"name": "a", "type": "string", "description": "", "nullable": True, "primary_key": False}
    doc = to_odcs(_contract(models={"fields": [legacy]}))
    _assert_valid(doc)
    assert not {"classification", "unique", "physicalType"} & _prop(doc).keys()
    field = from_odcs(doc).models["fields"][0]
    assert (field["classification"], field["unique"], field["physical_type"]) == ("", False, "")


@pytest.mark.parametrize("value", CLASSIFICATIONS)
def test_every_classification_validates_and_round_trips(value):
    field = {**FIELD, "classification": value}
    doc = to_odcs(_contract(models={"fields": [field]}))
    _assert_valid(doc)
    assert from_odcs(doc).models["fields"] == [field]


@pytest.mark.parametrize("overrides, key", [
    ({"password": SECRET}, "password"),
    ({"host": f"user:{SECRET}@db.example.com"}, "host"),
    ({"type": "s3"}, "type"),
    ({"catalog": ""}, "catalog"),
])
def test_bad_server_raises_naming_the_key_not_the_value(overrides, key):
    doc = to_odcs(_contract(servers=[DATABRICKS]))
    doc["servers"][0].update(overrides)
    with pytest.raises(OdcsParseError, match=key) as exc:
        from_odcs(doc)
    assert SECRET not in str(exc.value)


@pytest.mark.parametrize("mutate, key", [
    (lambda d: _prop(d).update(classification="secret"), "classification"),
    (lambda d: d["description"].update(customProperties=[]), "customProperties"),
    (lambda d: d["team"]["members"][0].update(dateIn="2026-01-01"), "dateIn"),
    (lambda d: d["support"][0].update(invitationUrl="https://example.com"), "invitationUrl"),
    (lambda d: d["team"].update(description="x"), "description"),
])
def test_unmodelled_value_is_not_dropped_silently(mutate, key):
    doc = to_odcs(FULL_CONTRACT)
    mutate(doc)
    with pytest.raises(OdcsParseError, match=key):
        from_odcs(doc)


@pytest.mark.parametrize("mutate, match", [
    (lambda d: d["team"]["members"][0].update(role=None), "role must be of type str"),
    (lambda d: d["team"]["members"][0].pop("username"), r"team.members\[0\] needs a username"),
    (lambda d: d["team"]["members"].append("bob"), "must be an object"),
    (lambda d: d["team"].update(name=7), "team name"),
    (lambda d: d["support"][0].update(channel={"a": 1}), "channel must be of type str"),
    (lambda d: d["support"][0].update(channel=" "), r"support\[0\] needs a channel"),
    (lambda d: d["support"][0].update(url="javascript:alert(1)"), "http, https or mailto"),
    (lambda d: d["description"].update(purpose=5), "description purpose"),
    (lambda d: d["servers"][0].update(environment=None), "environment must be text"),
    (lambda d: d["servers"][0].update(schema=2024), "schema_name must be text"),
    (lambda d: d.update(domain=["commerce"]), "domain"),
])
def test_value_the_api_would_refuse_is_not_stored(mutate, match):
    doc = to_odcs(FULL_CONTRACT)
    mutate(doc)
    with pytest.raises(OdcsParseError, match=match):
        from_odcs(doc)
