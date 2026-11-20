"""One quality rule, and the service levels, to and from ODCS. Pure, no I/O.

Raises plain ValueError; odcs.py wraps it. This module must not import odcs.py,
which imports it.
"""

from collections.abc import Mapping
from datetime import date
from typing import Any

from backend.domain.quality_rules import QUALITY_OPERATORS
from backend.use_cases.data_contract.parsed_contract import printable, unknown_keys

_RULE_KEYS = frozenset(
    {"type", "dimension", "metric", "unit", "arguments", "description"}
    | set(QUALITY_OPERATORS)
)
_CHECK_KEYS = ("metric", "unit", "arguments", *QUALITY_OPERATORS)
_SLA_KEYS = frozenset({"property", "value", "unit"})
# ODCS writes % and min. Files written by hand or by other tools use these too.
SLA_UNIT_ALIASES = {"percent": "%", "m": "min"}


def _object(item: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(item, Mapping):
        raise ValueError(f"{where} must be an object")
    return item


def rule_to_odcs(rule: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {"type": rule["type"]}
    if rule.get("dimension") is not None:
        item["dimension"] = rule["dimension"]
    if rule["type"] == "library":
        item["metric"] = rule["metric"]
        item[rule["operator"]] = rule["value"]
        if rule.get("unit") is not None:
            item["unit"] = rule["unit"]
        if rule["metric"] == "invalidValues":
            item["arguments"] = {"validValues": list(rule.get("valid_values") or [])}
    if rule.get("description"):
        item["description"] = rule["description"]
    return item


def _valid_values(arguments: Any) -> list[str]:
    if arguments is None:
        return []
    arguments = _object(arguments, "quality rule arguments")
    unknown = unknown_keys(arguments, frozenset({"validValues"}))
    if unknown:
        raise ValueError(f"quality rule arguments has unsupported keys: {unknown}")
    values = arguments.get("validValues") or []
    # A YAML scalar is a string, which would split into one value per character.
    if not isinstance(values, list):
        raise ValueError("quality rule validValues must be a list")
    if any(value is None or isinstance(value, Mapping | list) for value in values):
        raise ValueError("quality rule validValues can only hold scalar values")
    return [str(value) for value in values]


def rule_from_odcs(item: dict[str, Any], column: str) -> dict[str, Any]:
    kind = _object(item, "quality rule").get("type") or (
        "library" if "metric" in item else "text"
    )
    if kind not in ("library", "text"):
        raise ValueError(f"quality type {kind!r} is not supported")
    unknown = unknown_keys(item, _RULE_KEYS)
    if unknown:
        raise ValueError(f"quality rule has unsupported keys: {unknown}")

    rule: dict[str, Any] = {
        "type": kind,
        "dimension": item.get("dimension"),
        "column": column,
        "metric": None,
        "operator": None,
        "value": None,
        "unit": None,
        "valid_values": [],
        "description": item.get("description") or "",
    }
    if kind == "text":
        extra = [key for key in _CHECK_KEYS if key in item]
        if extra:
            raise ValueError(f"a text quality rule cannot carry {', '.join(extra)}")
        return rule

    operators = [operator for operator in QUALITY_OPERATORS if operator in item]
    if len(operators) != 1:
        raise ValueError("a library quality rule needs exactly one operator")
    rule["metric"] = item.get("metric")
    rule["operator"] = operators[0]
    rule["value"] = item[operators[0]]
    rule["unit"] = item.get("unit")
    rule["valid_values"] = _valid_values(item.get("arguments"))
    return rule


def sla_to_odcs(servicelevels: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    for prop in servicelevels.get("properties") or []:
        entry = {"property": prop["property"], "value": prop["value"]}
        if prop.get("unit") is not None:
            entry["unit"] = prop["unit"]
        entries.append(entry)
    return entries


def _sla_value(value: Any, where: str) -> Any:
    # YAML reads an unquoted date or timestamp as an object JSON cannot hold.
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, bool | Mapping | list):
        raise ValueError(f"{where} has no storable value")
    return value


def sla_from_odcs(items: Any) -> dict[str, Any]:
    """Shapes only; service_level_problems decides what may be stored."""
    if not isinstance(items, list):
        raise ValueError("slaProperties must be a list")
    properties = []
    for item in items:
        name = _object(item, "slaProperties entry").get("property")
        where = f"slaProperties entry {printable(name)}"
        unknown = unknown_keys(item, _SLA_KEYS)
        if unknown:
            raise ValueError(f"{where} has unsupported keys: {unknown}")
        unit = item.get("unit")
        if isinstance(unit, str):
            unit = SLA_UNIT_ALIASES.get(unit, unit)
        properties.append(
            {
                "property": name,
                "value": _sla_value(item.get("value"), where),
                "unit": unit,
            }
        )
    return {"properties": properties}
