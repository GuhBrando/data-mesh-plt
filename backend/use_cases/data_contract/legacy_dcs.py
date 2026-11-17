"""Reader for the legacy Data Contract Specification 0.9.3 files.

Kept only until the central repository is converted to ODCS. It reproduces the
reads the sync did before ODCS, without normalising anything.
"""

import uuid
from typing import Any

from backend.use_cases.data_contract.odcs import ParsedContract


def from_legacy_dcs(doc: dict[str, Any]) -> ParsedContract:
    info = doc.get("info", {})
    models_section = dict(doc.get("models", {}))
    quality = doc.get("quality", [])
    if quality:
        models_section["quality"] = quality
    return ParsedContract(
        id=uuid.UUID(str(doc["id"])),
        title=info.get("title", ""),
        version=info.get("version", "1.0.0"),
        owner=info.get("owner", ""),
        domain_name=info.get("domain", ""),
        tier=int(doc.get("x-tier", 4)),
        status=info.get("status", "draft"),
        models=models_section,
        servicelevels=doc.get("servicelevels", {}) or {},
    )
