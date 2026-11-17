"""Which quality rules the platform stores. Pure: no I/O, no backend imports.

Every library rule accepted here runs under datacontract-cli 1.2.9. The limits
below are what that tool executes, measured rule by rule: a rule it skips with a
warning, or one that breaks the whole run, is refused instead of stored.
"""

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

QUALITY_DIMENSIONS = (
    "accuracy",
    "completeness",
    "conformity",
    "consistency",
    "coverage",
    "timeliness",
    "uniqueness",
)
QUALITY_METRICS = (
    "nullValues",
    "missingValues",
    "invalidValues",
    "duplicateValues",
    "rowCount",
)
QUALITY_OPERATORS = (
    "mustBe",
    "mustNotBe",
    "mustBeGreaterThan",
    "mustBeGreaterOrEqualTo",
    "mustBeLessThan",
    "mustBeLessOrEqualTo",
)
QUALITY_UNITS = ("rows", "percent")
# The tool only executes unit percent on these; elsewhere it warns and skips.
PERCENT_METRICS = ("nullValues", "missingValues", "invalidValues")

_RULE_TYPES = ("library", "text")
# A valid value that does not cast to the column type fails every check of the run.
_CASTS: dict[str, Callable[[str], Any]] = {
    "integer": int,
    "float": float,
    "date": date.fromisoformat,
    "timestamp": datetime.fromisoformat,
}


def _enum_problem(rule: dict[str, Any]) -> str | None:
    if rule.get("type") not in _RULE_TYPES:
        return f"type must be one of {', '.join(_RULE_TYPES)}"
    allowed = (
        ("dimension", QUALITY_DIMENSIONS),
        ("metric", QUALITY_METRICS),
        ("operator", QUALITY_OPERATORS),
        ("unit", QUALITY_UNITS),
    )
    for key, values in allowed:
        if rule.get(key) is not None and rule[key] not in values:
            return f"{key} must be one of {', '.join(values)}"
    return None


def _text_problem(rule: dict[str, Any]) -> str | None:
    if not str(rule.get("description") or "").strip():
        return "a text rule needs a description"
    carries_check = any(
        rule.get(key) is not None for key in ("metric", "operator", "value", "unit")
    )
    if carries_check or rule.get("valid_values"):
        return "a text rule takes no metric, operator, value, unit or valid_values"
    return None


def _value_problem(rule: dict[str, Any]) -> str | None:
    value = rule.get("value")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "value must be a number"
    if value < 0:
        return "value cannot be negative"
    if rule.get("unit") == "percent" and value > 100:
        return "a percent value cannot exceed 100"
    return None


def _library_problem(rule: dict[str, Any]) -> str | None:
    metric = rule.get("metric")
    if metric is None or rule.get("operator") is None:
        return "a library rule needs a metric and an operator"
    problem = _value_problem(rule)
    if problem:
        return problem
    has_column = bool(rule.get("column"))
    if metric == "rowCount" and has_column:
        return "rowCount applies to the whole table and takes no column"
    if metric != "rowCount" and not has_column:
        return f"{metric} needs a column"
    if rule.get("unit") == "percent" and metric not in PERCENT_METRICS:
        return f"unit percent only runs with {', '.join(PERCENT_METRICS)}"
    has_valid_values = bool(rule.get("valid_values"))
    if metric == "invalidValues" and not has_valid_values:
        return "invalidValues needs valid_values"
    if metric != "invalidValues" and has_valid_values:
        return "valid_values only applies to invalidValues"
    return None


def _column_problem(rule: dict[str, Any], field_types: dict[str, Any]) -> str | None:
    column = rule.get("column") or ""
    if not column:
        return None
    if column not in field_types:
        return f"column {column!r} is not a schema field"
    cast = _CASTS.get(field_types[column])
    if cast is None:
        return None
    for value in rule.get("valid_values") or []:
        try:
            cast(value)
        except (TypeError, ValueError):
            return (
                f"valid value {value!r} does not cast to the"
                f" {field_types[column]} column {column}"
            )
    return None


def _rule_problem(rule: dict[str, Any], field_types: dict[str, Any]) -> str | None:
    problem = _enum_problem(rule)
    if problem:
        return problem
    shape = _text_problem if rule["type"] == "text" else _library_problem
    return shape(rule) or _column_problem(rule, field_types)


def find_quality_rule_problems(
    rules: list[dict[str, Any]], fields: list[dict[str, Any]]
) -> list[str]:
    """At most one message per rule, then one per (metric, column) collision."""
    field_types = {field.get("name"): field.get("type") for field in fields}
    problems = []
    for number, rule in enumerate(rules, start=1):
        problem = _rule_problem(rule, field_types)
        if problem:
            problems.append(f"quality rule {number}: {problem}")

    # Two library rules on one metric and column collide in the tool's result
    # set, and every check of the model fails with them.
    seen: set[tuple[Any, str]] = set()
    for number, rule in enumerate(rules, start=1):
        if rule.get("type") != "library":
            continue
        column = rule.get("column") or ""
        key = (rule.get("metric"), column)
        if key in seen:
            problems.append(
                f"quality rule {number}: {column or 'the table'} already has a"
                f" {rule.get('metric')} rule; datacontract-cli 1.2.9 cannot run two"
            )
        seen.add(key)
    return problems
