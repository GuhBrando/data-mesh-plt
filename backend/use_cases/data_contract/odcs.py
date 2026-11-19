"""Mapping between the internal data contract and ODCS v3.2.0. Pure, no I/O."""

import re
import unicodedata
import uuid
from collections.abc import Mapping
from typing import Any

from backend.domain.contract_metadata import (
    DESCRIPTION_KEYS,
    MEMBER_KEYS,
    SERVER_KEYS,
    SUPPORT_KEYS,
    empty_description,
    empty_server,
    server_problems,
    support_url_problem,
)
from backend.domain.contract_values import (
    CLASSIFICATIONS,
    CONTRACT_STATUSES,
    FIELD_TYPES,
    RULE_DIMENSIONS,
    RULE_OPERATORS,
    SLA_KEYS,
)
from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.parsed_contract import (
    ContractParseError,
    ParsedContract,
)

__all__ = [
    "ODCS_API_VERSION",
    "OdcsParseError",
    "ParsedContract",
    "from_odcs",
    "to_odcs",
]

ODCS_API_VERSION = "v3.2.0"
ODCS_KIND = "DataContract"


class OdcsParseError(ContractParseError):
    pass


_ODCS_STATUS = {"in_review": "proposed"}
_ODCS_LOGICAL_TYPE = {"float": "number"}
_ODCS_DIMENSION = {
    "completeness": "completeness",
    "uniqueness": "uniqueness",
    "freshness": "timeliness",
    "validity": "conformity",
    "integrity": "consistency",
}

# Bounded digits: int() of a long digit string is slow, and past 4300 digits it
# raises. A longer value is kept as text.
_SLA_VALUE = re.compile(r"(\d{1,15}(?:\.\d{1,15})?)\s*([a-zA-Z%]+)?")
_ODCS_UNIT = {"m": "min"}
_STORED_UNIT = {"min": "m", "percent": "%"}


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
    # No generated sentence: it would go stale as soon as a value is edited in Git.
    if rule.get("description"):
        out["description"] = rule["description"]
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
    sla = [
        _to_sla_entry(key, str(raw))
        for key, raw in (contract.servicelevels or {}).items()
        if raw
    ]
    if sla:
        doc["slaProperties"] = sla
    doc["customProperties"] = [{"property": "tier", "value": contract.tier}]
    return doc


_DB_STATUSES = frozenset(CONTRACT_STATUSES)
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
_RULE_KEYS = frozenset({"type", "dimension", "description", "customProperties"})
_RULE_REQUIRED_CUSTOM_KEYS = (
    "dmpltDimension",
    "dmpltOperator",
    "dmpltThreshold",
    "dmpltPosition",
)
_RULE_CUSTOM_KEYS = frozenset({*_RULE_REQUIRED_CUSTOM_KEYS, "dmpltColumn"})
_CUSTOM_ENTRY_KEYS = frozenset({"property", "value"})
_SLA_ENTRY_KEYS = frozenset({"property", "value", "unit"})
_SLA_KEYS = SLA_KEYS

_DB_STATUS = {odcs: stored for stored, odcs in _ODCS_STATUS.items()}
_STORED_TYPE = {_ODCS_LOGICAL_TYPE.get(t, t): t for t in FIELD_TYPES}
_MAX_LISTED_KEYS = 10


def _printable(value: Any) -> str:
    """A file value for an error message: control characters escaped."""
    return str(value).encode("unicode_escape").decode("ascii")


def _reject_unknown(keys: Any, allowed: frozenset[str], where: str) -> None:
    if not isinstance(keys, Mapping):
        raise OdcsParseError(f"{where} must be an object")
    unknown = sorted(_printable(key) for key in keys if key not in allowed)
    if unknown:
        listed = ", ".join(unknown[:_MAX_LISTED_KEYS])
        if len(unknown) > _MAX_LISTED_KEYS:
            listed += f" and {len(unknown) - _MAX_LISTED_KEYS} more"
        raise OdcsParseError(f"{where} has unsupported keys: {listed}")


def _custom_values(entries: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for entry in entries or []:
        name = entry["property"]
        where = f"customProperties entry {_printable(name)}"
        _reject_unknown(entry, _CUSTOM_ENTRY_KEYS, where)
        if name in values:
            raise OdcsParseError(f"{where} appears more than once")
        values[name] = entry["value"]
    return values


def _require(value: Any, kind: type, where: str) -> Any:
    # type() rather than isinstance: True must not pass as an int.
    if type(value) is not kind:
        raise OdcsParseError(f"{where} must be of type {kind.__name__}, got {value!r}")
    return value


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
    return _require(team.get("name", ""), str, "team name")


def _parse_rows(
    rows: Any, keys: tuple[str, ...], required: str, where: str
) -> list[dict[str, str]]:
    """Text rows, like the API takes them: every value a string, `required` set."""
    allowed = frozenset(keys)
    parsed = []
    for index, row in enumerate(rows or []):
        at = f"{where}[{index}]"
        _reject_unknown(row, allowed, at)
        values = {key: _require(row.get(key, ""), str, f"{at} {key}") for key in keys}
        if not values[required].strip():
            raise OdcsParseError(f"{at} needs a {required}")
        parsed.append(values)
    return parsed


def _parse_description(doc: dict[str, Any]) -> dict[str, str]:
    description = doc.get("description")
    if description is None:
        return empty_description()
    _reject_unknown(description, _DESCRIPTION_KEYS, "description")
    return {
        key: _require(description.get(key, ""), str, f"description {key}")
        for key in DESCRIPTION_KEYS
    }


def _parse_members(doc: dict[str, Any]) -> list[dict[str, str]]:
    team = doc.get("team") or {}
    return _parse_rows(team.get("members"), MEMBER_KEYS, "username", "team.members")


def _parse_support(doc: dict[str, Any]) -> list[dict[str, str]]:
    rows = _parse_rows(doc.get("support"), SUPPORT_KEYS, "channel", "support")
    for index, row in enumerate(rows):
        problem = support_url_problem(row["url"])
        if problem:
            raise OdcsParseError(f"support[{index}]: {problem}")
    return rows


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
    levels: dict[str, Any] = dict.fromkeys(_SLA_KEYS, "")
    seen: set[str] = set()
    for entry in doc.get("slaProperties") or []:
        key = entry["property"]
        _reject_unknown(entry, _SLA_ENTRY_KEYS, f"slaProperties entry {key}")
        if key in seen:
            raise OdcsParseError(f"slaProperties entry {key} appears more than once")
        seen.add(key)
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
    if dimension not in RULE_DIMENSIONS or operator not in RULE_OPERATORS:
        raise OdcsParseError(
            f"{where} has dmpltDimension {dimension!r} and dmpltOperator"
            f" {operator!r}; expected one of {', '.join(RULE_DIMENSIONS)}"
            f" and one of {', '.join(RULE_OPERATORS)}"
        )
    # The ODCS dimension is derived; a different one is an edit the model drops.
    odcs_dimension = _ODCS_DIMENSION[dimension]
    if rule.get("dimension", odcs_dimension) != odcs_dimension:
        raise OdcsParseError(f"{where} dimension does not match dmpltDimension")
    threshold = _require(custom["dmpltThreshold"], str, f"{where} dmpltThreshold")
    _require(column, str, f"{where} column")
    description = _require(rule.get("description", ""), str, f"{where} description")
    stored = {
        "dimension": dimension,
        "column": column,
        "operator": operator,
        "threshold": threshold,
        "description": description,
    }
    return _require(custom["dmpltPosition"], int, f"{where} dmpltPosition"), stored


def _parse_property(prop: dict[str, Any]) -> dict[str, Any]:
    name = prop.get("name")
    where = f"property {_printable(name)}"
    _reject_unknown(prop, _PROPERTY_KEYS, where)
    if not isinstance(name, str) or not name.strip():
        raise OdcsParseError(f"{where} needs a non-empty name")
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
        "description": _require(
            prop.get("description", ""), str, f"{where} description"
        ),
        "nullable": not _require(
            prop.get("required", False), bool, f"{where} required"
        ),
        "primary_key": _require(
            prop.get("primaryKey", False), bool, f"{where} primaryKey"
        ),
        "classification": classification,
        "unique": _require(prop.get("unique", False), bool, f"{where} unique"),
        "physical_type": _require(
            prop.get("physicalType", ""), str, f"{where} physicalType"
        ),
    }


def _check_schema_object(schema: dict[str, Any]) -> None:
    _reject_unknown(schema, _SCHEMA_KEYS, "schema")
    # The platform writes only these; another value is an edit it would drop.
    # The schema name is the slug of the title and is regenerated on every write.
    for key, written in (("logicalType", "object"), ("physicalType", "table")):
        if schema.get(key, written) != written:
            raise OdcsParseError(f"schema {key} must be {written!r}")


def _parse_models(doc: dict[str, Any]) -> dict[str, Any]:
    schemas = doc.get("schema") or []
    if len(schemas) > 1:
        raise OdcsParseError(
            f"contract has {len(schemas)} schema objects; at most one is supported"
        )
    fields: list[dict[str, Any]] = []
    positioned: list[tuple[Any, dict]] = []
    for schema in schemas:
        _check_schema_object(schema)
        for prop in schema.get("properties") or []:
            stored = _parse_property(prop)
            fields.append(stored)
            positioned.extend(
                _parse_rule(rule, stored["name"]) for rule in prop.get("quality") or []
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
        title=_require(doc.get("name", ""), str, "name"),
        # Not str(): an unquoted 1.10 loads as the float 1.1, and null as None.
        version=_require(doc.get("version", "1.0.0"), str, "version"),
        owner=_parse_owner(doc),
        domain_name=_require(doc.get("domain", ""), str, "domain"),
        tier=_parse_tier(doc),
        status=_parse_status(doc),
        models=_parse_models(doc),
        servicelevels=_parse_servicelevels(doc),
        description=_parse_description(doc),
        team_members=_parse_members(doc),
        support=_parse_support(doc),
        servers=_parse_servers(doc),
    )


def from_odcs(doc: dict[str, Any]) -> ParsedContract:
    try:
        return _parse(doc)
    except (AttributeError, KeyError, TypeError) as exc:
        raise OdcsParseError(f"malformed ODCS document: {exc!r}") from exc
