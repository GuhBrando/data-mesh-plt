"""Reader for the legacy Data Contract Specification 0.9.3 files.

Kept only until the central repository is converted to ODCS. A legacy file
holds service levels as strings and quality rules in the pre-ODCS shape, so
both are converted here to the shapes the platform stores now. The rules
follow the conversion the data migration applies to rows it cannot run: a text
rule that keeps the old values in its description. Models that are not lists
of objects are refused, because the platform could not write them back, and so
is anything the API would refuse to store.
"""

import json
import re
import uuid
from typing import Any

from backend.domain.quality_rules import find_quality_rule_problems
from backend.domain.service_levels import service_level_problems
from backend.use_cases.data_contract.odcs_quality import SLA_UNIT_ALIASES
from backend.use_cases.data_contract.parsed_contract import (
    ContractParseError,
    ParsedContract,
    unknown_keys,
)

# Bounded digits: int() of a long digit string is slow, and past 4300 digits it
# raises. A longer value is kept as text.
_SLA_VALUE = re.compile(r"(\d{1,15}(?:\.\d{1,15})?)\s*([a-zA-Z%]+)?")
_DIMENSIONS = {
    "completeness": "completeness",
    "uniqueness": "uniqueness",
    "freshness": "timeliness",
    "validity": "conformity",
    "integrity": "consistency",
}


def _service_levels(levels: Any) -> dict[str, Any]:
    if not levels:
        return {"properties": []}
    if not isinstance(levels, dict):
        raise ContractParseError("servicelevels must be an object")
    properties = []
    for key, raw in levels.items():
        text = "" if raw is None else str(raw).strip()
        if not text:
            continue
        match = _SLA_VALUE.fullmatch(text)
        if match:
            number, unit = match.groups()
            value: Any = float(number) if "." in number else int(number)
            unit = SLA_UNIT_ALIASES.get(unit, unit)
        else:
            value, unit = text, None
        properties.append({"property": key, "value": value, "unit": unit})
    problems = service_level_problems(properties)
    if problems:
        raise ContractParseError("; ".join(problems))
    return {"properties": properties}


def _stored_rule(**values: Any) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "type": "text",
        "dimension": None,
        "column": "",
        "metric": None,
        "operator": None,
        "value": None,
        "unit": None,
        "valid_values": [],
        "description": "",
    }
    unknown = unknown_keys(values, frozenset(rule))
    if unknown:
        raise ContractParseError(f"quality rule has unsupported keys: {unknown}")
    return {**rule, **values}


def _jsonb_text(value: Any) -> str:
    """The value as Postgres prints jsonb, which the data migration quotes."""

    def ordered(item: Any) -> Any:
        # jsonb keeps object keys sorted by length, then bytes.
        if isinstance(item, dict):
            keys = sorted(item, key=lambda key: (len(str(key).encode()), str(key)))
            return {str(key): ordered(item[key]) for key in keys}
        if isinstance(item, list):
            return [ordered(element) for element in item]
        return item

    return json.dumps(ordered(value), ensure_ascii=False, default=str)


def _legacy_text(rule: dict[str, Any]) -> str:
    if "threshold" not in rule:
        # A SodaCL or other rule with no threshold keeps its whole content.
        return f"[legacy rule: {_jsonb_text(rule)}]"
    values = " ".join(
        f"{key}={'' if rule.get(key) is None else rule.get(key)}"
        for key in ("dimension", "column", "operator", "threshold")
    )
    return f"[legacy rule: {values}]"


def _quality_rule(rule: Any, field_names: set[Any]) -> dict[str, Any]:
    if not isinstance(rule, dict):
        return _stored_rule(description=f"[legacy rule: {_jsonb_text(rule)}]")
    if rule.get("type") in ("library", "text"):
        # Already the stored shape: fill what is missing and let the domain rules
        # decide, as the API would.
        return _stored_rule(**rule)
    column = rule.get("column") or ""
    description = " ".join(
        part
        for part in (str(rule.get("description") or "").strip(), _legacy_text(rule))
        if part
    )
    return _stored_rule(
        dimension=_DIMENSIONS.get(rule.get("dimension")),
        column=column if column in field_names else "",
        description=description,
    )


def _models(doc: dict[str, Any]) -> dict[str, Any]:
    models = doc.get("models", {})
    if not isinstance(models, dict):
        raise ContractParseError("models must be an object")
    models_section = dict(models)
    fields = models_section.get("fields", [])
    if not isinstance(fields, list) or not all(isinstance(f, dict) for f in fields):
        raise ContractParseError("models.fields must be a list of objects")
    # As the sync before ODCS did, rules at the top level replace models.quality.
    rules = doc.get("quality") or models_section.get("quality")
    if isinstance(rules, dict):
        rules = [rules]
    if rules and not isinstance(rules, list):
        raise ContractParseError("quality must be a list")
    if rules:
        names = {field.get("name") for field in fields}
        quality = [_quality_rule(rule, names) for rule in rules]
        problems = find_quality_rule_problems(quality, fields)
        if problems:
            raise ContractParseError("; ".join(problems))
        models_section["quality"] = quality
    return models_section


def from_legacy_dcs(doc: dict[str, Any]) -> ParsedContract:
    info = doc.get("info", {})
    return ParsedContract(
        id=uuid.UUID(str(doc["id"])),
        title=info.get("title", ""),
        version=info.get("version", "1.0.0"),
        owner=info.get("owner", ""),
        domain_name=info.get("domain", ""),
        tier=int(doc.get("x-tier", 4)),
        status=info.get("status", "draft"),
        models=_models(doc),
        servicelevels=_service_levels(doc.get("servicelevels")),
    )
