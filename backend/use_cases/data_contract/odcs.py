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


_DB_STATUSES = frozenset({"draft", "in_review", "active", "deprecated"})
_DOCUMENT_KEYS = frozenset(
    {
        "apiVersion",
        "kind",
        "id",
        "name",
        "version",
        "status",
        "domain",
        "team",
        "schema",
        "slaProperties",
        "customProperties",
    }
)
_TEAM_KEYS = frozenset({"name"})
_SCHEMA_KEYS = frozenset(
    {"name", "logicalType", "physicalType", "properties", "quality"}
)
_PROPERTY_KEYS = frozenset(
    {"name", "description", "logicalType", "required", "primaryKey", "quality"}
)
_RULE_KEYS = frozenset({"type", "dimension", "description", "customProperties"})
_RULE_CUSTOM_KEYS = frozenset(
    {
        "dmpltDimension",
        "dmpltOperator",
        "dmpltThreshold",
        "dmpltColumn",
        "dmpltPosition",
    }
)
_RULE_REQUIRED_CUSTOM_KEYS = (
    "dmpltDimension",
    "dmpltOperator",
    "dmpltThreshold",
    "dmpltPosition",
)
_SLA_ENTRY_KEYS = frozenset({"property", "value", "unit"})
_SLA_KEYS = ("freshness", "availability", "retention", "latency")

_DB_STATUS = {odcs: stored for stored, odcs in _ODCS_STATUS.items()}
_STORED_TYPE = {
    "string": "string",
    "integer": "integer",
    "number": "float",
    "boolean": "boolean",
    "date": "date",
    "timestamp": "timestamp",
}


def _reject_unknown(keys: Any, allowed: frozenset[str], where: str) -> None:
    unknown = sorted(str(key) for key in keys if key not in allowed)
    if unknown:
        raise OdcsParseError(f"{where} has unsupported keys: {', '.join(unknown)}")


def _custom_values(entries: Any) -> dict[str, Any]:
    return {entry["property"]: entry["value"] for entry in entries or []}


def _parse_id(doc: dict[str, Any]) -> uuid.UUID:
    raw = doc["id"]
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        raise OdcsParseError(f"contract id {raw!r} is not a UUID") from None


def _parse_owner(doc: dict[str, Any]) -> str:
    team = doc.get("team")
    if team is None:
        return ""
    if isinstance(team, list):
        raise OdcsParseError("team must be an object, not the deprecated array")
    _reject_unknown(team, _TEAM_KEYS, "team")
    return team.get("name", "")


def _parse_tier(doc: dict[str, Any]) -> int:
    custom = _custom_values(doc.get("customProperties"))
    _reject_unknown(custom, frozenset({"tier"}), "contract customProperties")
    tier = custom.get("tier", 4)
    if type(tier) is not int or not 1 <= tier <= 4:
        raise OdcsParseError(f"tier must be an integer from 1 to 4, got {tier!r}")
    return tier


def _parse_status(doc: dict[str, Any]) -> str:
    raw = doc.get("status", "draft")
    status = _DB_STATUS.get(raw, raw)
    if status not in _DB_STATUSES:
        names = ", ".join(sorted(_ODCS_STATUS.get(name, name) for name in _DB_STATUSES))
        raise OdcsParseError(f"status {raw!r} is not accepted; expected one of {names}")
    return status


def _parse_servicelevels(doc: dict[str, Any]) -> dict[str, Any]:
    levels: dict[str, Any] = dict.fromkeys(_SLA_KEYS, "")
    for entry in doc.get("slaProperties") or []:
        key = entry["property"]
        _reject_unknown(entry, _SLA_ENTRY_KEYS, f"slaProperties entry {key}")
        value = entry.get("value")
        if value is None or isinstance(value, bool):
            raise OdcsParseError(f"slaProperties entry {key} has no storable value")
        levels[key] = _sla_text(value, entry.get("unit"))
    return levels


def _parse_rule(rule: dict[str, Any], prop_name: str | None) -> tuple[Any, dict]:
    custom = _custom_values(rule.get("customProperties"))
    column = prop_name if prop_name is not None else custom.get("dmpltColumn", "")
    where = f"quality rule on {column}" if column else "quality rule on the schema"

    _reject_unknown(rule, _RULE_KEYS, where)
    _reject_unknown(custom, _RULE_CUSTOM_KEYS, where)
    if rule.get("type") != "text":
        raise OdcsParseError(
            f"{where} has type {rule.get('type')!r}; only text rules can be stored"
        )
    missing = [key for key in _RULE_REQUIRED_CUSTOM_KEYS if key not in custom]
    if missing:
        raise OdcsParseError(f"{where} is missing {', '.join(missing)}")

    dimension = custom["dmpltDimension"]
    operator = custom["dmpltOperator"]
    threshold = custom["dmpltThreshold"]
    description = rule.get("description", "")
    if description == _rule_sentence(dimension, column, operator, threshold):
        description = ""
    stored = {
        "dimension": dimension,
        "column": column,
        "operator": operator,
        "threshold": threshold,
        "description": description,
    }
    return custom["dmpltPosition"], stored


def _parse_property(prop: dict[str, Any]) -> dict[str, Any]:
    name = prop.get("name")
    _reject_unknown(prop, _PROPERTY_KEYS, f"property {name}")
    logical = prop.get("logicalType")
    if logical not in _STORED_TYPE:
        raise OdcsParseError(
            f"property {name} has logicalType {logical!r}, which cannot be stored"
        )
    return {
        "name": name,
        "type": _STORED_TYPE[logical],
        "description": prop.get("description", ""),
        "nullable": not prop.get("required", False),
        "primary_key": prop.get("primaryKey", False),
    }


def _parse_models(doc: dict[str, Any]) -> dict[str, Any]:
    schemas = doc.get("schema") or []
    if len(schemas) > 1:
        raise OdcsParseError(
            f"contract has {len(schemas)} schema objects; at most one is supported"
        )
    fields: list[dict[str, Any]] = []
    positioned: list[tuple[Any, dict]] = []
    for schema in schemas:
        _reject_unknown(schema, _SCHEMA_KEYS, "schema")
        for prop in schema.get("properties") or []:
            field = _parse_property(prop)
            fields.append(field)
            positioned.extend(
                _parse_rule(rule, field["name"]) for rule in prop.get("quality") or []
            )
        positioned.extend(
            _parse_rule(rule, None) for rule in schema.get("quality") or []
        )
    positioned.sort(key=lambda pair: pair[0])
    return {"fields": fields, "quality": [rule for _, rule in positioned]}


def _parse(doc: dict[str, Any]) -> ParsedContract:
    api_version = doc.get("apiVersion")
    if not str(api_version).startswith("v3."):
        raise OdcsParseError(f"unsupported apiVersion {api_version!r}: expected v3.x")
    kind = doc.get("kind")
    if kind != ODCS_KIND:
        raise OdcsParseError(f"unsupported kind {kind!r}: expected {ODCS_KIND}")
    _reject_unknown(doc, _DOCUMENT_KEYS, "contract")
    return ParsedContract(
        id=_parse_id(doc),
        title=doc.get("name", ""),
        version=str(doc.get("version", "1.0.0")),
        owner=_parse_owner(doc),
        domain_name=doc.get("domain", ""),
        tier=_parse_tier(doc),
        status=_parse_status(doc),
        models=_parse_models(doc),
        servicelevels=_parse_servicelevels(doc),
    )


def from_odcs(doc: dict[str, Any]) -> ParsedContract:
    try:
        return _parse(doc)
    except (AttributeError, KeyError, TypeError) as exc:
        raise OdcsParseError(f"malformed ODCS document: {exc!r}") from exc
