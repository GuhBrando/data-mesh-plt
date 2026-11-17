"""Mapping between the internal data contract and ODCS v3.2.0. Pure, no I/O."""

import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Any

from backend.domain.entities.data_contract import DataContract

ODCS_API_VERSION = "v3.2.0"
ODCS_KIND = "DataContract"


class OdcsParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedContract:
    id: uuid.UUID
    title: str
    version: str
    owner: str
    domain_name: str
    tier: int
    status: str
    models: dict[str, Any]
    servicelevels: dict[str, Any]


_ODCS_STATUS = {"in_review": "proposed"}
_ODCS_LOGICAL_TYPE = {"float": "number"}
_ODCS_DIMENSION = {
    "completeness": "completeness",
    "uniqueness": "uniqueness",
    "freshness": "timeliness",
    "validity": "conformity",
    "integrity": "consistency",
}

_SLA_VALUE = re.compile(r"(\d+(?:\.\d+)?)\s*([a-zA-Z%]+)?")
_ODCS_UNIT = {"m": "min"}
_STORED_UNIT = {"min": "m", "percent": "%"}


def _rule_sentence(dimension: Any, column: str, operator: Any, threshold: Any) -> str:
    target = f"column {column}" if column else "the table"
    return f"{str(dimension).capitalize()} of {target} must be {operator} {threshold}."


def _sla_text(value: Any, unit: str | None) -> str:
    return f"{value}{_STORED_UNIT.get(unit, unit) or ''}"


def _to_sla_entry(key: str, raw: str) -> dict[str, Any]:
    match = _SLA_VALUE.fullmatch(raw)
    if match:
        number, unit = match.groups()
        value = float(number) if "." in number else int(number)
        odcs_unit = _ODCS_UNIT.get(unit, unit)
        if _sla_text(value, odcs_unit) == raw:
            entry: dict[str, Any] = {"property": key, "value": value}
            if odcs_unit:
                entry["unit"] = odcs_unit
            return entry
    return {"property": key, "value": raw}


def _schema_name(title: str) -> str:
    folded = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", folded.lower()).strip("_") or "contract"


def _to_property(field: dict[str, Any]) -> dict[str, Any]:
    field_type = field.get("type")
    return {
        "name": field.get("name"),
        "description": field.get("description", ""),
        "logicalType": _ODCS_LOGICAL_TYPE.get(field_type, field_type),
        "required": not field.get("nullable", True),
        "primaryKey": bool(field.get("primary_key", False)),
    }


def _to_rule(rule: dict[str, Any], position: int, known_column: bool) -> dict[str, Any]:
    dimension = rule.get("dimension")
    column = rule.get("column") or ""
    operator = rule.get("operator")
    threshold = rule.get("threshold")

    custom = [
        {"property": "dmpltDimension", "value": dimension},
        {"property": "dmpltOperator", "value": operator},
        {"property": "dmpltThreshold", "value": threshold},
    ]
    if column and not known_column:
        custom.append({"property": "dmpltColumn", "value": column})
    custom.append({"property": "dmpltPosition", "value": position})

    out: dict[str, Any] = {"type": "text"}
    if dimension in _ODCS_DIMENSION:
        out["dimension"] = _ODCS_DIMENSION[dimension]
    out["description"] = rule.get("description") or _rule_sentence(
        dimension, column, operator, threshold
    )
    out["customProperties"] = custom
    return out


def _to_schema(contract: DataContract) -> list[dict[str, Any]]:
    models = contract.models or {}
    fields = models.get("fields") or []
    rules = models.get("quality") or []
    if not fields and not rules:
        return []

    properties = [_to_property(field) for field in fields]
    by_name = {prop["name"]: prop for prop in properties if prop["name"]}
    table_rules = []
    for position, rule in enumerate(rules):
        owner = by_name.get(rule.get("column") or "")
        emitted = _to_rule(rule, position, owner is not None)
        if owner is None:
            table_rules.append(emitted)
        else:
            owner.setdefault("quality", []).append(emitted)

    schema: dict[str, Any] = {
        "name": _schema_name(contract.title),
        "logicalType": "object",
        "physicalType": "table",
    }
    if properties:
        schema["properties"] = properties
    if table_rules:
        schema["quality"] = table_rules
    return [schema]


def to_odcs(contract: DataContract) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "apiVersion": ODCS_API_VERSION,
        "kind": ODCS_KIND,
        "id": str(contract.id),
        "name": contract.title,
        "version": contract.version,
        "status": _ODCS_STATUS.get(contract.status, contract.status),
        "domain": contract.domain,
        "team": {"name": contract.owner},
    }
    schema = _to_schema(contract)
    if schema:
        doc["schema"] = schema
    sla = [
        _to_sla_entry(key, str(raw))
        for key, raw in (contract.servicelevels or {}).items()
        if raw
    ]
    if sla:
        doc["slaProperties"] = sla
    doc["customProperties"] = [{"property": "tier", "value": contract.tier}]
    return doc
