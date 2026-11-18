"""Mapping between the internal data contract and ODCS v3.2.0. Pure, no I/O."""

import re
import unicodedata
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from backend.domain.contract_metadata import (
    CLASSIFICATIONS,
    DESCRIPTION_KEYS,
    MEMBER_KEYS,
    SERVER_KEYS,
    SUPPORT_KEYS,
    empty_description,
    empty_server,
    server_problems,
)
from backend.domain.entities.data_contract import DataContract
from backend.domain.quality_rules import QUALITY_OPERATORS, find_quality_rule_problems
from backend.use_cases.data_contract.odcs_quality import (
    rule_from_odcs,
    rule_to_odcs,
    sla_from_odcs,
    sla_to_odcs,
)

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
    description: dict[str, str] = field(default_factory=empty_description)
    team_members: list[dict[str, Any]] = field(default_factory=list)
    support: list[dict[str, Any]] = field(default_factory=list)
    servers: list[dict[str, Any]] = field(default_factory=list)


_ODCS_STATUS = {"in_review": "proposed"}
_ODCS_LOGICAL_TYPE = {"float": "number"}


def _rule_sentence(dimension: Any, column: str, operator: Any, threshold: Any) -> str:
    target = f"column {column}" if column else "the table"
    return f"{str(dimension).capitalize()} of {target} must be {operator} {threshold}."


def _schema_name(title: str) -> str:
    folded = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", folded.lower()).strip("_") or "contract"


def _to_property(stored: dict[str, Any]) -> dict[str, Any]:
    field_type = stored.get("type")
    prop: dict[str, Any] = {
        "name": stored.get("name"),
        "description": stored.get("description", ""),
        "logicalType": _ODCS_LOGICAL_TYPE.get(field_type, field_type),
        "required": not stored.get("nullable", True),
        "primaryKey": bool(stored.get("primary_key", False)),
    }
    # Fields stored before these attributes existed do not carry them.
    if stored.get("physical_type"):
        prop["physicalType"] = stored["physical_type"]
    if stored.get("classification"):
        prop["classification"] = stored["classification"]
    if stored.get("unique"):
        prop["unique"] = True
    return prop


def _filled(row: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    """The row's non-empty values, in key order."""
    return {key: row[key] for key in keys if row.get(key) not in (None, "")}


def _to_server(row: Mapping[str, Any]) -> dict[str, Any]:
    server = _filled(row, SERVER_KEYS)
    if "schema_name" in server:
        server["schema"] = server.pop("schema_name")
    return server


def _to_team(contract: DataContract) -> dict[str, Any]:
    team: dict[str, Any] = {"name": contract.owner}
    members = [_filled(row, MEMBER_KEYS) for row in contract.team_members or []]
    if members:
        team["members"] = members
    return team


def _to_schema(contract: DataContract) -> list[dict[str, Any]]:
    models = contract.models or {}
    fields = models.get("fields") or []
    rules = models.get("quality") or []
    if not fields and not rules:
        return []

    properties = [_to_property(field) for field in fields]
    by_name = {prop["name"]: prop for prop in properties if prop["name"]}
    table_rules = []
    for rule in rules:
        owner = by_name.get(rule.get("column") or "")
        emitted = rule_to_odcs(rule)
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
    }
    description = _filled(contract.description or {}, DESCRIPTION_KEYS)
    if description:
        doc["description"] = description
    doc["team"] = _to_team(contract)
    support = [_filled(row, SUPPORT_KEYS) for row in contract.support or []]
    if support:
        doc["support"] = support
    servers = [_to_server(row) for row in contract.servers or []]
    if servers:
        doc["servers"] = servers
    schema = _to_schema(contract)
    if schema:
        doc["schema"] = schema
    sla = sla_to_odcs(contract.servicelevels or {})
    if sla:
        doc["slaProperties"] = sla
    doc["customProperties"] = [{"property": "tier", "value": contract.tier}]
    return doc


_DB_STATUSES = frozenset({"draft", "in_review", "active", "deprecated", "retired"})
_DOCUMENT_KEYS = frozenset(
    {
        "apiVersion",
        "kind",
        "id",
        "name",
        "version",
        "status",
        "domain",
        "description",
        "team",
        "support",
        "servers",
        "schema",
        "slaProperties",
        "customProperties",
    }
)
_TEAM_KEYS = frozenset({"name", "members"})
_DESCRIPTION_KEYS = frozenset(DESCRIPTION_KEYS)
_MEMBER_KEYS = frozenset(MEMBER_KEYS)
_SUPPORT_KEYS = frozenset(SUPPORT_KEYS)
_SERVER_KEYS = frozenset(
    "schema" if key == "schema_name" else key for key in SERVER_KEYS
)
_SCHEMA_KEYS = frozenset(
    {"name", "logicalType", "physicalType", "properties", "quality"}
)
_PROPERTY_KEYS = frozenset(
    {
        "name",
        "description",
        "logicalType",
        "required",
        "primaryKey",
        "quality",
        "classification",
        "unique",
        "physicalType",
    }
)
_RULE_KEYS = frozenset(
    {
        "type",
        "dimension",
        "description",
        "customProperties",
        "metric",
        "unit",
        "arguments",
        *QUALITY_OPERATORS,
    }
)
# The custom properties a text rule written by Plan 1 carries. They are read
# once, into the description, and never written again.
_RULE_CUSTOM_KEYS = frozenset(
    {
        "dmpltDimension",
        "dmpltOperator",
        "dmpltThreshold",
        "dmpltColumn",
        "dmpltPosition",
    }
)
_SLA_ENTRY_KEYS = frozenset({"property", "value", "unit"})

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
    if not isinstance(keys, Mapping):
        raise OdcsParseError(f"{where} must be an object")
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


def _parse_rows(
    rows: Any, allowed: frozenset[str], keys: tuple[str, ...], where: str
) -> list[dict[str, Any]]:
    parsed = []
    for index, row in enumerate(rows or []):
        _reject_unknown(row, allowed, f"{where}[{index}]")
        parsed.append({key: row.get(key, "") for key in keys})
    return parsed


def _parse_description(doc: dict[str, Any]) -> dict[str, str]:
    description = doc.get("description")
    if description is None:
        return empty_description()
    _reject_unknown(description, _DESCRIPTION_KEYS, "description")
    return {key: description.get(key, "") for key in DESCRIPTION_KEYS}


def _parse_members(doc: dict[str, Any]) -> list[dict[str, Any]]:
    team = doc.get("team") or {}
    return _parse_rows(team.get("members"), _MEMBER_KEYS, MEMBER_KEYS, "team.members")


def _parse_servers(doc: dict[str, Any]) -> list[dict[str, Any]]:
    servers = []
    for index, row in enumerate(doc.get("servers") or []):
        where = f"servers[{index}]"
        _reject_unknown(row, _SERVER_KEYS, where)
        server = empty_server()
        for key, value in row.items():
            server["schema_name" if key == "schema" else key] = value
        problems = server_problems(server)
        if problems:
            # server_problems names keys only, so no value reaches the message.
            raise OdcsParseError(f"{where}: {problems[0]}")
        servers.append(server)
    return servers


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
    entries = doc.get("slaProperties") or []
    for entry in entries:
        key = entry["property"]
        _reject_unknown(entry, _SLA_ENTRY_KEYS, f"slaProperties entry {key}")
    try:
        return sla_from_odcs(entries)
    except ValueError as exc:
        raise OdcsParseError(str(exc)) from exc


def _is_plan1_rule(item: Any) -> bool:
    """A text rule written before library rules: only dmplt* custom properties."""
    if not isinstance(item, Mapping) or item.get("type") != "text":
        return False
    custom = item.get("customProperties")
    if not isinstance(custom, list) or not custom:
        return False
    return all(
        isinstance(entry, Mapping) and entry.get("property") in _RULE_CUSTOM_KEYS
        for entry in custom
    )


def _legacy_description(item: Mapping[str, Any], prop_name: str | None) -> str:
    """The text the data migration writes for the same stored rule."""
    custom = _custom_values(item.get("customProperties"))

    def text(key: str) -> str:
        value = custom.get(key)
        return "" if value is None else str(value)

    column = prop_name if prop_name is not None else text("dmpltColumn")
    dimension, operator = text("dmpltDimension"), text("dmpltOperator")
    threshold = text("dmpltThreshold")
    description = str(item.get("description") or "").strip(" ")
    # Plan 1 wrote this sentence for a rule stored with an empty description.
    if description == _rule_sentence(dimension, column, operator, threshold):
        description = ""
    suffix = (
        f"[legacy rule: dimension={dimension} column={column}"
        f" operator={operator} threshold={threshold}]"
    )
    return " ".join(part for part in (description, suffix) if part)


def _parse_library_or_text_rule(item: Any, column: str) -> dict[str, Any]:
    where = f"quality rule on {column}" if column else "quality rule on the schema"
    _reject_unknown(item, _RULE_KEYS, where)
    try:
        return rule_from_odcs(item, column)
    except ValueError as exc:
        raise OdcsParseError(f"{where}: {exc}") from exc


def _parse_quality_item(item: Any, prop_name: str | None) -> dict[str, Any]:
    if not _is_plan1_rule(item):
        return _parse_library_or_text_rule(item, prop_name or "")
    plain = {key: value for key, value in item.items() if key != "customProperties"}
    rule = _parse_library_or_text_rule(plain, prop_name or "")
    rule["description"] = _legacy_description(item, prop_name)
    return rule


def _parse_property(prop: dict[str, Any]) -> dict[str, Any]:
    name = prop.get("name")
    _reject_unknown(prop, _PROPERTY_KEYS, f"property {name}")
    logical = prop.get("logicalType")
    if logical not in _STORED_TYPE:
        raise OdcsParseError(
            f"property {name} has logicalType {logical!r}, which cannot be stored"
        )
    classification = prop.get("classification", "")
    if classification not in ("", *CLASSIFICATIONS):
        raise OdcsParseError(
            f"property {name} has a classification outside {', '.join(CLASSIFICATIONS)}"
        )
    return {
        "name": name,
        "type": _STORED_TYPE[logical],
        "description": prop.get("description", ""),
        "nullable": not prop.get("required", False),
        "primary_key": prop.get("primaryKey", False),
        "classification": classification,
        "unique": prop.get("unique", False),
        "physical_type": prop.get("physicalType", ""),
    }


def _parse_models(doc: dict[str, Any]) -> dict[str, Any]:
    schemas = doc.get("schema") or []
    if len(schemas) > 1:
        raise OdcsParseError(
            f"contract has {len(schemas)} schema objects; at most one is supported"
        )
    fields: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] = []

    def collect(items: Any, prop_name: str | None) -> None:
        rules.extend(_parse_quality_item(item, prop_name) for item in items or [])

    for schema in schemas:
        _reject_unknown(schema, _SCHEMA_KEYS, "schema")
        for prop in schema.get("properties") or []:
            stored = _parse_property(prop)
            fields.append(stored)
            collect(prop.get("quality"), stored["name"])
        collect(schema.get("quality"), None)
    problems = find_quality_rule_problems(rules, fields)
    if problems:
        raise OdcsParseError("; ".join(problems))
    return {"fields": fields, "quality": rules}


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
        description=_parse_description(doc),
        team_members=_parse_members(doc),
        support=_parse_rows(doc.get("support"), _SUPPORT_KEYS, SUPPORT_KEYS, "support"),
        servers=_parse_servers(doc),
    )


def from_odcs(doc: dict[str, Any]) -> ParsedContract:
    try:
        return _parse(doc)
    except (AttributeError, KeyError, TypeError) as exc:
        raise OdcsParseError(f"malformed ODCS document: {exc!r}") from exc
