import pytest

from backend.domain.quality_rules import (
    QUALITY_OPERATORS,
    find_quality_rule_problems,
)
from tests.quality_rule_builders import library_rule, text_rule


FIELDS = [{"name": "id", "type": "integer"}, {"name": "email", "type": "string"},
          {"name": "joined", "type": "date"}]
lib, txt = library_rule, text_rule

RUNNABLE = [
    lib(), lib(unit=None), lib(dimension=None),
    lib(unit="percent", operator="mustBeLessOrEqualTo", value=1),
    lib(metric="missingValues", unit="percent"),
    lib(metric="invalidValues", valid_values=["a@x.io"], unit="percent"),
    lib(metric="invalidValues", column="id", valid_values=["1", "2"]),
    lib(metric="invalidValues", column="joined", valid_values=["2026-01-01"]),
    lib(metric="duplicateValues", column="id"),
    lib(metric="rowCount", column="", operator="mustBeGreaterOrEqualTo", value=5),
    txt(), txt(column="email"),
    *[lib(operator=op) for op in QUALITY_OPERATORS],
]

@pytest.mark.parametrize("rule", RUNNABLE)
def test_accepts_rules_the_tool_runs(rule):
    assert find_quality_rule_problems([rule], FIELDS) == []

@pytest.mark.parametrize(("rule", "fragment"), [
    (lib(metric="duplicateValues", column="id", unit="percent"), "percent"),
    (lib(metric="rowCount", column="", unit="percent"), "percent"),
    (lib(metric="rowCount", column="id"), "whole table"),
    (lib(column=""), "needs a column"),
    (lib(metric="duplicateValues", column=""), "needs a column"),
    (lib(metric="invalidValues", valid_values=[]), "valid_values"),
    (lib(valid_values=["x"]), "valid_values"),
    (lib(metric="invalidValues", column="id", valid_values=["1", "abc"]), "'abc'"),
    (lib(metric="invalidValues", column="joined", valid_values=["soon"]), "'soon'"),
    (lib(column="ghost"), "'ghost'"),
    (txt(column="ghost"), "'ghost'"),
    (lib(value=None), "value"), (lib(value="0"), "value"), (lib(value=True), "value"),
    (lib(value=-1), "negative"),
    (lib(unit="percent", value=101), "100"),
    (lib(metric="sql"), "metric"), (lib(operator="mustBeBetween"), "operator"),
    (lib(unit="ms"), "unit"), (lib(dimension="freshness"), "dimension"),
    (lib(type="sql"), "type"),
    (txt(description="  "), "description"),
    (txt(metric="nullValues"), "text rule"),
])
def test_rejects_rules_the_tool_cannot_run(rule, fragment):
    problems = find_quality_rule_problems([rule], FIELDS)
    assert len(problems) == 1
    assert problems[0].startswith("quality rule 1: ")
    assert fragment in problems[0]

def test_rejects_second_rule_with_same_metric_and_column():
    rules = [lib(), lib(operator="mustBeLessThan", value=5)]
    assert find_quality_rule_problems(rules, FIELDS) == [
        "quality rule 2: email already has a nullValues rule;"
        " datacontract-cli 1.2.9 cannot run two"
    ]

def test_same_metric_on_another_column_and_text_rules_are_accepted():
    rules = [lib(), lib(column="id"), txt(column="email"), txt(column="email")]
    assert find_quality_rule_problems(rules, FIELDS) == []
