"""Rules for the contract metadata sections. Pure: no I/O, no backend imports.

Pydantic and the ODCS reader both enforce these, so the API and a synced file
accept the same servers.
"""

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")
SERVER_TYPES = ("databricks", "postgres", "azure", "local")

DESCRIPTION_KEYS = ("purpose", "usage", "limitations")
MEMBER_KEYS = ("username", "name", "role")
SUPPORT_KEYS = ("channel", "url", "tool", "scope")
SERVER_KEYS = (
    "server",
    "type",
    "environment",
    "host",
    "catalog",
    "schema_name",
    "port",
    "database",
    "location",
    "format",
    "path",
)

# type -> (required keys, optional keys), beyond server, type and environment.
# ODCS v3.2.0 rejects any other key for the type.
SERVER_RULES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "databricks": (("catalog", "schema_name"), ("host",)),
    "postgres": (("host", "port", "database", "schema_name"), ()),
    "azure": (("location", "format"), ()),
    "local": (("path", "format"), ()),
}
_COMMON_KEYS = ("server", "type", "environment")
_TYPE_KEYS = tuple(key for key in SERVER_KEYS if key not in _COMMON_KEYS)
_HOST = re.compile(r"[A-Za-z0-9.-]+")


def empty_description() -> dict[str, str]:
    return dict.fromkeys(DESCRIPTION_KEYS, "")


def empty_server() -> dict[str, Any]:
    return {key: None if key == "port" else "" for key in SERVER_KEYS}


def _absent(value: Any) -> bool:
    return value is None or value == ""


def _host_problem(host: Any) -> str | None:
    if not isinstance(host, str) or not _HOST.fullmatch(host):
        return "host must be a bare host name, without scheme, user, path or query"
    return None


def _location_problem(location: Any) -> str | None:
    try:
        parts = urlsplit(location)
        has_secret_part = bool(parts.password or parts.query or parts.fragment)
    except (ValueError, TypeError, AttributeError):
        return "location is not a valid URL"
    if not parts.scheme:
        return "location must be a URL with a scheme"
    if has_secret_part:
        return "location must not carry a password, query string or fragment"
    return None


def _port_problem(port: Any) -> str | None:
    if type(port) is not int or not 1 <= port <= 65535:
        return "port must be an integer from 1 to 65535"
    return None


_VALUE_CHECKS = {
    "host": _host_problem,
    "location": _location_problem,
    "port": _port_problem,
}


def server_problems(server: Mapping[str, Any]) -> list[str]:
    """One message per problem. Messages name keys and never repeat a value."""
    problems: list[str] = []
    name = server.get("server")
    if not isinstance(name, str) or not name.strip():
        problems.append("server needs a name")

    kind = server.get("type")
    if not isinstance(kind, str) or kind not in SERVER_RULES:
        problems.append(f"type must be one of {', '.join(SERVER_TYPES)}")
        return problems

    required, optional = SERVER_RULES[kind]
    for key in _TYPE_KEYS:
        value = server.get(key)
        if _absent(value):
            if key in required:
                problems.append(f"{key} is required for a {kind} server")
            continue
        if key not in required and key not in optional:
            problems.append(f"{key} is not used by a {kind} server")
            continue
        check = _VALUE_CHECKS.get(key)
        problem = check(value) if check else None
        if problem:
            problems.append(problem)
    return problems
