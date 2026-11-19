"""The quality and SLA data migration, run against a throwaway Postgres.

Set TEST_DATABASE_URL to an empty database. The fixture creates the catalog
schema itself, so it fails on a database that already has one, which keeps the
test away from real data. Every test runs in one transaction that is rolled back.
"""

import json
import os
from pathlib import Path

import asyncpg
import pytest

from tests.quality_rule_builders import library_rule

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not set")

SQL_FILE = (
    Path(__file__).parents[2]
    / "database/migrations/20261101000004_odcs_quality_and_sla.sql"
)
DDL = """
CREATE SCHEMA catalog;
CREATE TABLE catalog.data_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL DEFAULT 'x',
    models JSONB NOT NULL,
    servicelevels JSONB NOT NULL
        DEFAULT '{"freshness":"","availability":"","retention":"","latency":""}'
);
"""
FIELDS = [{"name": "id"}, {"name": "email"}]
TEXT = object()


@pytest.fixture
async def db():
    conn = await asyncpg.connect(DATABASE_URL)
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute(DDL)
        yield conn
    finally:
        await tx.rollback()
        await conn.close()


async def run_migration(conn) -> None:
    await conn.execute(SQL_FILE.read_text(encoding="utf-8"))


async def insert(conn, models, servicelevels) -> object:
    return await conn.fetchval(
        "INSERT INTO catalog.data_contracts (models, servicelevels)"
        " VALUES ($1::jsonb, $2::jsonb) RETURNING id",
        json.dumps(models),
        json.dumps(servicelevels),
    )


async def read(conn, row_id) -> tuple[dict, dict]:
    row = await conn.fetchrow(
        "SELECT models, servicelevels FROM catalog.data_contracts WHERE id = $1",
        row_id,
    )
    return json.loads(row["models"]), json.loads(row["servicelevels"])


async def migrate(conn, models, servicelevels) -> tuple[dict, dict]:
    row_id = await insert(conn, models, servicelevels)
    await run_migration(conn)
    return await read(conn, row_id)


def old(dimension="completeness", column="email", operator=">=", threshold="99%",
        description=""):
    return {"dimension": dimension, "column": column, "operator": operator,
            "threshold": threshold, "description": description}


async def rules_after(conn, *rules) -> list[dict]:
    models, _ = await migrate(conn, {"fields": FIELDS, "quality": list(rules)}, {})
    return models["quality"]


@pytest.mark.parametrize(("rule", "expected"), [
    (old(), {"type": "library", "metric": "nullValues", "operator": "mustBeLessOrEqualTo",
             "value": 1, "unit": "percent"}),
    (old(threshold="99.9"), {"metric": "nullValues", "value": 0.1}),
    (old(threshold=99), {"metric": "nullValues", "value": 1}),
    (old(dimension="uniqueness", column="id", threshold="100%"),
     {"type": "library", "metric": "duplicateValues", "operator": "mustBeLessOrEqualTo",
      "value": 0, "unit": "rows"}),
    (old(dimension="uniqueness", column="id", threshold="99"), TEXT),
    (old(threshold="0.99"), TEXT), (old(threshold="1"), TEXT), (old(threshold="150"), TEXT),
    (old(threshold="abc"), TEXT), (old(threshold="24h"), TEXT), (old(threshold=""), TEXT),
    (old(operator="<=", threshold="5"), TEXT), (old(operator="=", threshold="100"), TEXT),
    (old(column=""), TEXT),
])
async def test_rule_conversion(db, rule, expected):
    [got] = await rules_after(db, rule)
    if expected is TEXT:
        assert (got["type"], got["metric"], got["value"]) == ("text", None, None)
        assert "[legacy rule: dimension=" in got["description"]
    else:
        assert {k: got[k] for k in expected} == expected


async def test_text_rule_keeps_old_values_and_maps_dimension(db):
    assert await rules_after(db, old("freshness", "id", "<=", "24h", "Daily")) == [{
        "type": "text", "dimension": "timeliness", "column": "id", "metric": None,
        "operator": None, "value": None, "unit": None, "valid_values": [],
        "description": "Daily [legacy rule: dimension=freshness column=id operator=<= threshold=24h]",
    }]


async def test_unknown_column_moves_into_description(db):
    [got] = await rules_after(db, old(column="ghost"))
    assert got["column"] == ""
    assert "column=ghost" in got["description"]


async def test_dimensions_are_mapped(db):
    rules = await rules_after(
        db, *(old(dimension=d, operator="=") for d in
              ("validity", "integrity", "completeness", "uniqueness"))
    )
    assert [r["dimension"] for r in rules] == [
        "conformity", "consistency", "completeness", "uniqueness",
    ]


async def test_second_rule_on_same_metric_and_column_becomes_text(db):
    first, second = await rules_after(db, old(), old(description="second"))
    assert first["type"] == "library"
    assert second["type"] == "text"
    assert second["description"].startswith("second [legacy rule: ")


async def test_rule_already_in_new_format_wins_its_metric_and_column(db):
    new = library_rule(column="email")
    migrated, kept = await rules_after(db, old(), new)
    assert migrated["type"] == "text"
    assert kept == new


async def test_rule_already_in_new_format_is_untouched(db):
    rule = library_rule(column="email", operator="mustBeLessOrEqualTo", value=2.5,
                        unit="percent", description="kept")
    assert await rules_after(db, rule) == [rule]


async def test_unreadable_entries_become_text(db):
    rules = await rules_after(db, "free text rule", 7, {"type": "SodaCL", "specification": "x"})
    assert [(r["type"], r["dimension"]) for r in rules] == [("text", None)] * 3
    assert [r["description"] for r in rules] == [
        '[legacy rule: "free text rule"]',
        "[legacy rule: 7]",
        '[legacy rule: {"type": "SodaCL", "specification": "x"}]',
    ]


async def test_quality_object_is_wrapped_in_a_list(db):
    models, _ = await migrate(db, {"fields": FIELDS, "quality": old()}, {})
    assert [r["metric"] for r in models["quality"]] == ["nullValues"]


@pytest.mark.parametrize("models", [
    {"fields": FIELDS},
    {"fields": FIELDS, "extra": {"keep": True}, "quality": []},
])
async def test_models_without_rules_are_untouched(db, models):
    got, _ = await migrate(db, models, {})
    assert got == models


async def test_null_quality_becomes_an_empty_list(db):
    got, _ = await migrate(db, {"fields": FIELDS, "quality": None}, {})
    assert got == {"fields": FIELDS, "quality": []}


async def test_service_levels_are_split(db):
    _, sla = await migrate(db, {"fields": []}, {
        "freshness": "24h", "availability": "99.9%", "retention": "365d", "latency": "30m",
    })
    assert sla == {"properties": [
        {"property": "freshness", "value": 24, "unit": "h"},
        {"property": "availability", "value": 99.9, "unit": "%"},
        {"property": "retention", "value": 365, "unit": "d"},
        {"property": "latency", "value": 30, "unit": "min"},
    ]}


@pytest.mark.parametrize("levels", [
    {"freshness": "", "availability": "", "retention": "", "latency": ""}, {},
])
async def test_empty_service_levels_become_an_empty_list(db, levels):
    _, sla = await migrate(db, {"fields": []}, levels)
    assert sla == {"properties": []}


async def test_unparseable_and_extra_service_levels_are_kept(db):
    _, sla = await migrate(db, {"fields": []}, {
        "frequency": "1d", "latency": None, "retention": "P1D", "availability": "   ",
        "freshness": "best effort",
    })
    assert sla == {"properties": [
        {"property": "freshness", "value": "best effort", "unit": None},
        {"property": "retention", "value": "P1D", "unit": None},
        {"property": "frequency", "value": 1, "unit": "d"},
    ]}
    _, sla = await migrate(db, {"fields": []}, {"availability": "99.50 percent", "latency": "30"})
    assert sla == {"properties": [
        {"property": "availability", "value": 99.5, "unit": "%"},
        {"property": "latency", "value": 30, "unit": None},
    ]}


async def test_service_levels_already_in_new_format_are_untouched(db):
    levels = {"properties": [{"property": "freshness", "value": 24, "unit": "h"}]}
    _, sla = await migrate(db, {"fields": []}, levels)
    assert sla == levels


async def test_second_run_changes_nothing(db):
    seeds = [
        ({"fields": FIELDS, "quality": [old(), old(), old(column="ghost"), "free"]},
         {"freshness": "24h", "availability": "best effort"}),
        ({"fields": FIELDS, "quality": [library_rule(column="email")]}, {}),
        ({"fields": FIELDS}, {"properties": []}),
    ]
    for models, levels in seeds:
        await insert(db, models, levels)
    snapshot = "SELECT models, servicelevels FROM catalog.data_contracts ORDER BY id"
    await run_migration(db)
    first = [tuple(r) for r in await db.fetch(snapshot)]
    await run_migration(db)
    assert [tuple(r) for r in await db.fetch(snapshot)] == first


async def test_new_rows_default_to_the_new_service_level_shape(db):
    await run_migration(db)
    row_id = await db.fetchval(
        "INSERT INTO catalog.data_contracts (models) VALUES ('{}'::jsonb) RETURNING id"
    )
    _, sla = await read(db, row_id)
    assert sla == {"properties": []}
