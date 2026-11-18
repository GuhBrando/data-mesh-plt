"""Reads a contract file from the central repository, in either format."""

from typing import Any

import yaml
from yaml.events import AliasEvent

from backend.use_cases.data_contract.legacy_dcs import from_legacy_dcs
from backend.use_cases.data_contract.odcs import from_odcs
from backend.use_cases.data_contract.parsed_contract import (
    ContractParseError,
    ParsedContract,
)

# A contract is a few kilobytes; a file this large is a mistake or an attack.
MAX_CONTRACT_CHARS = 1_000_000


class _NoAliasLoader(yaml.SafeLoader):
    """SafeLoader without aliases: an alias bomb expands exponentially when read."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(AliasEvent):
            raise ContractParseError("YAML aliases are not allowed in contract files")
        return super().compose_node(parent, index)


def load_contract_yaml(content: str) -> Any:
    if len(content) > MAX_CONTRACT_CHARS:
        raise ContractParseError(
            f"contract file is larger than {MAX_CONTRACT_CHARS} characters"
        )
    return yaml.load(content, Loader=_NoAliasLoader)  # nosec B506 - SafeLoader subclass


def is_legacy_document(doc: dict[str, Any]) -> bool:
    # The old sync read any mapping through `info`, marker or not.
    return "dataContractSpecification" in doc or (
        "info" in doc and "apiVersion" not in doc
    )


def parse_contract_document(doc: dict[str, Any]) -> ParsedContract:
    if not isinstance(doc, dict):
        raise ContractParseError("contract file is not a YAML mapping")
    if is_legacy_document(doc):
        return from_legacy_dcs(doc)
    return from_odcs(doc)
