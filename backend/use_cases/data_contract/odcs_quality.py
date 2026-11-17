"""One quality rule, and the service levels, to and from ODCS. Pure, no I/O.

Raises plain ValueError; odcs.py wraps it. This module must not import odcs.py,
which imports it.
"""

from typing import Any

from backend.domain.quality_rules import QUALITY_OPERATORS

_RULE_KEYS = frozenset(
    {"type", "dimension", "metric", "unit", "arguments", "description"}
    | set(QUALITY_OPERATORS)
)
_CHECK_KEYS = ("metric", "unit", "arguments", *QUALITY_OPERATORS)
_SLA_KEYS = frozenset({"property", "value", "unit"})
# ODCS writes % and min. Files written by hand or by other tools use these too.
_SLA_UNIT_ALIASES = {"percent": "%", "m": "min"}


def _unknown(keys: Any, allowed: frozenset[str]) -> str:
    return ", ".join(sorted(str(key) for key in keys if key not in allowed))


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
    unknown = _unknown(arguments, frozenset({"validValues"}))
    if unknown:
        raise ValueError(f"quality rule arguments has unsupported keys: {unknown}")
    values = arguments.get("validValues") or []
    if any(value is None for value in values):
        raise ValueError("quality rule validValues cannot hold an empty value")
    return [str(value) for value in values]


def rule_from_odcs(item: dict[str, Any], column: str) -> dict[str, Any]:
    kind = item.get("type") or ("library" if "metric" in item else "text")
    if kind not in ("library", "text"):
        raise ValueError(f"quality type {kind!r} is not supported")
    unknown = _unknown(item, _RULE_KEYS)
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


def sla_from_odcs(items: list[dict[str, Any]]) -> dict[str, Any]:
    properties = []
    for item in items:
        name = item["property"]
        unknown = _unknown(item, _SLA_KEYS)
        if unknown:
            raise ValueError(
                f"slaProperties entry {name} has unsupported keys: {unknown}"
            )
        value = item.get("value")
        if value is None:
            raise ValueError(f"slaProperties entry {name} has no storable value")
        if isinstance(value, bool) or not isinstance(value, int | float):
            # YAML reads an unquoted timestamp as a datetime, which JSON cannot hold.
            value = str(value)
        unit = item.get("unit")
        properties.append(
            {
                "property": name,
                "value": value,
                "unit": _SLA_UNIT_ALIASES.get(unit, unit),
            }
        )
    return {"properties": properties}
