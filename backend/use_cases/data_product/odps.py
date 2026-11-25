"""Exports a data product as an Open Data Product Standard (ODPS) v1.1.0 document.

Pure, no I/O. The document is built from the aggregate in the platform's
snake_case names and passed once through `_odps`, which renames every key to
ODPS camelCase and leaves out what is empty, as `to_odcs` does. One mapping
serves every section. Platform-only fields (the repository URL, lineage and the
contract summaries on ports) are never exported.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC
from typing import TYPE_CHECKING, Any

from backend.use_cases.data_contract.yaml_builder import dump_odcs

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.entities.data_product import (
        DataProduct,
        InputPort,
        ManagementPort,
        OutputPort,
    )

ODPS_API_VERSION = "v1.1.0"
ODPS_KIND = "DataProduct"
# Read on the platform's side only: lineage and the referenced contract as it is.
_READ_ONLY = frozenset({"contract", "produced_by", "consumed_by"})
# A custom property's value is user data: exported as given, keys and all.
_USER_DATA = "value"


def _camel(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(word.capitalize() for word in rest)


def _empty(value: Any) -> bool:
    return value is None or value is False or value in ("", [], {})


def _odps(value: Any) -> Any:
    """`value` with ODPS key names and without empty entries."""
    if isinstance(value, dict):
        items = (
            (key, item if key == _USER_DATA else _odps(item))
            for key, item in value.items()
        )
        return {
            _camel(key): item
            for key, item in items
            if key == _USER_DATA or not _empty(item)
        }
    if isinstance(value, (list, tuple)):
        return [item for item in map(_odps, value) if not _empty(item)]
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _port(port: InputPort | OutputPort | ManagementPort) -> dict[str, Any]:
    fields = {
        f.name: getattr(port, f.name)
        for f in dataclasses.fields(port)
        if f.name not in _READ_ONLY
    }
    if "input_contracts" in fields:
        fields["input_contracts"] = [
            {"id": ref.contract_id, "version": ref.version}
            for ref in fields["input_contracts"]
        ]
    return fields


def _timestamp(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def to_odps(product: DataProduct) -> dict[str, Any]:
    return _odps(
        {
            "api_version": ODPS_API_VERSION,
            "kind": ODPS_KIND,
            "id": product.id,
            "name": product.name,
            "version": product.version,
            "status": product.status,
            "domain": product.domain,
            "tenant": product.tenant,
            "type": product.type,
            # Derived from status, so it can never disagree with it.
            "deprecated": product.deprecated,
            "description": product.description,
            "tags": product.tags,
            "synonyms": product.synonyms,
            "context": product.context,
            "authoritative_definitions": product.authoritative_definitions,
            "custom_properties": product.custom_properties,
            "input_ports": [_port(p) for p in product.input_ports],
            "output_ports": [_port(p) for p in product.output_ports],
            "management_ports": [_port(p) for p in product.management_ports],
            "support": product.support,
            "team": product.team,
            "product_created_ts": _timestamp(product.created_at),
        }
    )


def odps_yaml(product: DataProduct) -> str:
    """The document as YAML, written like the platform's contract files."""
    return dump_odcs(to_odps(product))
