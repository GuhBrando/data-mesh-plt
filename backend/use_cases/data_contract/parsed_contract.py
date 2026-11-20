"""The contract a file in the central repository describes, whatever its format.

Format readers (ODCS, the legacy DCS) produce a ParsedContract and raise
ContractParseError, so callers depend on neither format module.
"""

import uuid
from dataclasses import dataclass
from typing import Any


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
