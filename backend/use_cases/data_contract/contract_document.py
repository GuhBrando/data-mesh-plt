"""Reads a contract file from the central repository, in either format."""

from typing import Any

from backend.use_cases.data_contract.legacy_dcs import from_legacy_dcs
from backend.use_cases.data_contract.odcs import (
    OdcsParseError,
    ParsedContract,
    from_odcs,
)


def parse_contract_document(doc: dict[str, Any]) -> ParsedContract:
    if not isinstance(doc, dict):
        raise OdcsParseError("contract file is not a YAML mapping")
    if "dataContractSpecification" in doc:
        return from_legacy_dcs(doc)
    return from_odcs(doc)
