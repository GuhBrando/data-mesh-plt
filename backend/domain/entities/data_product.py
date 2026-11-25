"""The data product aggregate, as the Open Data Product Standard (ODPS) v1.1.0
models it: a product publishes output ports and reads input ports, and a port
may reference an ODCS contract by id and version.

The product owns its ports: they are created, changed and removed only through
it. Contracts are another aggregate, referenced by (contract_id, version) only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable
    from datetime import datetime

PRODUCT_STATUSES = ("proposed", "draft", "active", "deprecated", "retired")
RETIRED_PRODUCT = "retired"
STATUS_RULE = f"Status must be one of: {', '.join(PRODUCT_STATUSES)}"

# The descriptive ODPS sections, stored as the API validated them. The aggregate
# carries them without reading them: no product rule depends on their content.
PRODUCT_SECTIONS = (
    "version",
    "type",
    "tenant",
    "tags",
    "synonyms",
    "context",
    "team",
    "support",
    "custom_properties",
    "authoritative_definitions",
)
_TEXT_SECTIONS = frozenset({"version", "type", "tenant"})
_OBJECT_SECTIONS = frozenset({"context", "team"})
# Everything an edit may change; the rest is identity or read-only.
EDITABLE_FIELDS = (
    "name",
    "description",
    "domain_id",
    "status",
    *PRODUCT_SECTIONS,
    "input_ports",
    "output_ports",
    "management_ports",
)


def empty_product_description() -> dict[str, str]:
    return {"purpose": "", "usage": "", "limitations": ""}


def _empty(section: str) -> Any:
    if section in _TEXT_SECTIONS:
        return None
    return {} if section in _OBJECT_SECTIONS else []


_DEPRECATED_STATUSES = frozenset({"deprecated", RETIRED_PRODUCT})


class DataProductRuleError(Exception):
    """One or more product rules are broken. `messages` holds one line per rule,
    written for the person who sent the product."""

    def __init__(self, messages: list[str]):
        super().__init__("; ".join(messages))
        self.messages = messages


@dataclass(frozen=True)
class ContractRef:
    """An ODPS `inputContracts` entry: the contract version an output is built from."""

    contract_id: uuid.UUID
    version: str


@dataclass(frozen=True)
class ContractSummary:
    """The referenced contract as it is now. Read-only, filled on read."""

    title: str
    status: str
    version: str
    domain: str


@dataclass(frozen=True)
class ProductRef:
    """Another product seen from a port, for lineage. Read-only, filled on read."""

    id: uuid.UUID
    name: str
    status: str


@dataclass(frozen=True)
class InputPort:
    name: str
    contract_id: uuid.UUID | None = None
    version: str | None = None
    deprecated: bool = False
    authoritative_definitions: tuple[dict[str, Any], ...] = ()
    tags: tuple[str, ...] = ()
    custom_properties: tuple[dict[str, Any], ...] = ()
    id: uuid.UUID | None = None
    contract: ContractSummary | None = field(default=None, compare=False)
    # Products whose output ports carry the same contract version.
    produced_by: tuple[ProductRef, ...] = field(default=(), compare=False)


@dataclass(frozen=True)
class OutputPort:
    name: str
    contract_id: uuid.UUID | None = None
    version: str | None = None
    type: str | None = None
    description: str | None = None
    deprecated: bool = False
    authoritative_definitions: tuple[dict[str, Any], ...] = ()
    input_contracts: tuple[ContractRef, ...] = ()
    tags: tuple[str, ...] = ()
    custom_properties: tuple[dict[str, Any], ...] = ()
    # ODPS allows these three on output ports only.
    synonyms: tuple[dict[str, Any], ...] = ()
    context: dict[str, Any] = field(default_factory=dict)
    sbom: tuple[dict[str, Any], ...] = ()
    id: uuid.UUID | None = None
    contract: ContractSummary | None = field(default=None, compare=False)
    # Products whose input ports read the same contract version.
    consumed_by: tuple[ProductRef, ...] = field(default=(), compare=False)


@dataclass(frozen=True)
class ManagementPort:
    """How to observe or control the product: ODPS `managementPorts`."""

    name: str
    content: str
    type: str = "rest"
    url: str | None = None
    channel: str | None = None
    description: str | None = None
    deprecated: bool = False
    tags: tuple[str, ...] = ()
    custom_properties: tuple[dict[str, Any], ...] = ()
    authoritative_definitions: tuple[dict[str, Any], ...] = ()
    id: uuid.UUID | None = None


@dataclass(frozen=True)
class PortUsage:
    """One port that references a contract, seen from the contract."""

    product_id: uuid.UUID
    product_name: str
    domain: str
    status: str
    role: str
    port_name: str
    contract_id: uuid.UUID
    version: str


class DataProduct:
    def __init__(
        self,
        *,
        name: str,
        domain_id: uuid.UUID,
        description: dict[str, Any] | None = None,
        status: str = "draft",
        input_ports: Iterable[InputPort] = (),
        output_ports: Iterable[OutputPort] = (),
        management_ports: Iterable[ManagementPort] = (),
        id: uuid.UUID | None = None,
        domain: str = "",
        repo_url: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        **sections: Any,
    ):
        unknown = sorted(set(sections) - set(PRODUCT_SECTIONS))
        if unknown:
            raise TypeError(f"Unknown data product field: {', '.join(unknown)}")
        self.id = id
        self.name = name
        self.description = (
            description if description is not None else empty_product_description()
        )
        self.domain_id = domain_id
        self.domain = domain
        self.status = status
        for section in PRODUCT_SECTIONS:
            value = sections.get(section)
            setattr(self, section, _empty(section) if value is None else value)
        self.input_ports = tuple(input_ports)
        self.output_ports = tuple(output_ports)
        self.management_ports = tuple(management_ports)
        self.repo_url = repo_url
        self.created_at = created_at
        self.updated_at = updated_at
        broken = self._broken_rules()
        if broken:
            raise DataProductRuleError(broken)

    @property
    def deprecated(self) -> bool:
        return self.status in _DEPRECATED_STATUSES

    def revised(self, **changes: Any) -> DataProduct:
        """The product after an edit: `changes` replace editable fields, the rest
        keeps its value, and identity and read-only fields are kept."""
        unknown = sorted(set(changes) - set(EDITABLE_FIELDS))
        if unknown:
            raise TypeError(f"Not an editable field: {', '.join(unknown)}")
        status = changes.get("status", self.status)
        if self.status == RETIRED_PRODUCT and status != RETIRED_PRODUCT:
            raise DataProductRuleError(["A retired data product cannot change status"])
        values = {name: getattr(self, name) for name in EDITABLE_FIELDS} | changes
        return DataProduct(
            **values,
            id=self.id,
            domain=self.domain,
            repo_url=self.repo_url,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def _broken_rules(self) -> list[str]:
        broken = []
        if self.status not in PRODUCT_STATUSES:
            broken.append(STATUS_RULE)
        if not self.output_ports:
            broken.append("A data product needs at least one output")
        own_inputs = {
            ContractRef(p.contract_id, p.version)
            for p in self.input_ports
            if p.contract_id is not None and p.version is not None
        }
        for output in self.output_ports:
            broken.extend(
                f"Output {output.name} is built from version {ref.version} of"
                f" contract {ref.contract_id}, which is not one of this product's"
                " inputs"
                for ref in output.input_contracts
                if ref not in own_inputs
            )
        return broken
