"""Reader for the legacy Data Contract Specification 0.9.3 files.

Kept only until the central repository is converted to ODCS. A legacy file
holds service levels as strings and quality rules in the pre-ODCS shape, so
both are converted here to the shapes the platform stores now. The rules
follow the conversion the data migration applies to rows it cannot run: a text
rule that keeps the old values in its description.
"""

import json
import re
import uuid
from typing import Any

from backend.use_cases.data_contract.odcs import ParsedContract

_SLA_VALUE = re.compile(r"(\d+(?:\.\d+)?)\s*([a-zA-Z%]+)?")
_SLA_UNITS = {"percent": "%", "m": "min"}
_DIMENSIONS = {
    "completeness": "completeness",
    "uniqueness": "uniqueness",
    "freshness": "timeliness",
    "validity": "conformity",
    "integrity": "consistency",
}


def _service_levels(levels: Any) -> dict[str, Any]:
    properties = []
    for key, raw in (levels or {}).items():
        text = "" if raw is None else str(raw).strip()
        if not text:
            continue
        match = _SLA_VALUE.fullmatch(text)
        if match:
            number, unit = match.groups()
            value: Any = float(number) if "." in number else int(number)
            unit = _SLA_UNITS.get(unit, unit)
        else:
            value, unit = text, None
        properties.append({"property": key, "value": value, "unit": unit})
    return {"properties": properties}


def _text_rule(dimension: Any, column: str, description: str) -> dict[str, Any]:
    return {
        "type": "text",
        "dimension": dimension,
        "column": column,
        "metric": None,
        "operator": None,
        "value": None,
        "unit": None,
        "valid_values": [],
        "description": description,
    }


def _quality_rule(rule: Any, field_names: set[Any]) -> dict[str, Any]:
    if not isinstance(rule, dict):
        return _text_rule(None, "", f"[legacy rule: {json.dumps(rule)}]")
    if rule.get("type") in ("library", "text"):
        return rule
    column = rule.get("column") or ""
    values = " ".join(
        f"{key}={'' if rule.get(key) is None else rule.get(key)}"
        for key in ("dimension", "column", "operator", "threshold")
    )
    description = " ".join(
        part
        for part in (
            str(rule.get("description") or "").strip(),
            f"[legacy rule: {values}]",
        )
        if part
    )
    return _text_rule(
        _DIMENSIONS.get(rule.get("dimension")),
        column if column in field_names else "",
        description,
    )


def from_legacy_dcs(doc: dict[str, Any]) -> ParsedContract:
    info = doc.get("info", {})
    models_section = dict(doc.get("models", {}))
    quality = doc.get("quality", [])
    if quality:
        fields = models_section.get("fields") or []
        names = {field.get("name") for field in fields if isinstance(field, dict)}
        models_section["quality"] = [_quality_rule(rule, names) for rule in quality]
    return ParsedContract(
        id=uuid.UUID(str(doc["id"])),
        title=info.get("title", ""),
        version=info.get("version", "1.0.0"),
        owner=info.get("owner", ""),
        domain_name=info.get("domain", ""),
        tier=int(doc.get("x-tier", 4)),
        status=info.get("status", "draft"),
        models=models_section,
        servicelevels=_service_levels(doc.get("servicelevels")),
    )
