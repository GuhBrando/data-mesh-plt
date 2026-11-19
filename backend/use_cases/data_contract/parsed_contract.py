"""The contract a file in the central repository describes, whatever its format.

Format readers (ODCS, the legacy DCS) produce a ParsedContract and raise
ContractParseError, so callers depend on neither format module.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.domain.contract_metadata import empty_description


class ContractParseError(ValueError):
    """A contract file the platform cannot store as it is."""


_MAX_LISTED_KEYS = 10


def printable(value: Any) -> str:
    """A file value for an error message: control characters escaped."""
    return str(value).encode("unicode_escape").decode("ascii")


def unknown_keys(keys: Any, allowed: frozenset[str]) -> str | None:
    """The keys outside `allowed`, escaped and capped for an error message."""
    unknown = sorted(printable(key) for key in keys if key not in allowed)
    if not unknown:
        return None
    listed = ", ".join(unknown[:_MAX_LISTED_KEYS])
    if len(unknown) > _MAX_LISTED_KEYS:
        listed += f" and {len(unknown) - _MAX_LISTED_KEYS} more"
    return listed


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
