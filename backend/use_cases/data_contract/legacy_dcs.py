"""Reader for the legacy Data Contract Specification 0.9.3 files.

Kept only until the central repository is converted to ODCS. It reproduces the
reads the sync did before ODCS, and refuses only what the platform could not
write back: models that are not lists of objects.
"""

import uuid
from typing import Any

from backend.use_cases.data_contract.parsed_contract import (
    ContractParseError,
    ParsedContract,
)


def _require_objects(items: Any, where: str) -> None:
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise ContractParseError(f"{where} must be a list of objects")


def _models(doc: dict[str, Any]) -> dict[str, Any]:
    models = doc.get("models", {})
    if not isinstance(models, dict):
        raise ContractParseError("models must be an object")
    models_section = dict(models)
    for key in ("fields", "quality"):
        if key in models_section:
            _require_objects(models_section[key], f"models.{key}")
    quality = doc.get("quality", [])
    if quality:
        _require_objects(quality, "quality")
        models_section["quality"] = quality
    return models_section


def from_legacy_dcs(doc: dict[str, Any]) -> ParsedContract:
    info = doc.get("info", {})
    return ParsedContract(
        id=uuid.UUID(str(doc["id"])),
        title=info.get("title", ""),
        version=info.get("version", "1.0.0"),
        owner=info.get("owner", ""),
        domain_name=info.get("domain", ""),
        tier=int(doc.get("x-tier", 4)),
        status=info.get("status", "draft"),
        models=_models(doc),
        servicelevels=doc.get("servicelevels", {}) or {},
    )
