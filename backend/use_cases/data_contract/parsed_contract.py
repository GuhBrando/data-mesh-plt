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
