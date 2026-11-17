"""Stored-shape quality rules for the backend tests."""

from typing import Any


def library_rule(**overrides: Any) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "type": "library",
        "dimension": "completeness",
        "column": "email",
        "metric": "nullValues",
        "operator": "mustBe",
        "value": 0,
        "unit": "rows",
        "valid_values": [],
        "description": "",
    }
    return {**rule, **overrides}


def text_rule(**overrides: Any) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "type": "text",
        "dimension": "consistency",
        "column": "",
        "metric": None,
        "operator": None,
        "value": None,
        "unit": None,
        "valid_values": [],
        "description": "Totals reconcile with the ledger.",
    }
    return {**rule, **overrides}
