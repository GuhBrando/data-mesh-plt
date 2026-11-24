"""The data product aggregate, as the Open Data Product Standard (ODPS) v1.1.0
models it: a product publishes output ports and reads input ports, and a port
may reference an ODCS contract by id and version.

The product owns its ports: they are created, changed and removed only through
it. Contracts are another aggregate, referenced by (contract_id, version) only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable
    from datetime import datetime

PRODUCT_STATUSES = ("proposed", "draft", "active", "deprecated", "retired")
RETIRED_PRODUCT = "retired"
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
    authoritative_definitions: tuple[dict[str, str], ...] = ()
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
    authoritative_definitions: tuple[dict[str, str], ...] = ()
    input_contracts: tuple[ContractRef, ...] = ()
    id: uuid.UUID | None = None
    contract: ContractSummary | None = field(default=None, compare=False)
    # Products whose input ports read the same contract version.
    consumed_by: tuple[ProductRef, ...] = field(default=(), compare=False)


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
        description: str,
        domain_id: uuid.UUID,
        status: str = "draft",
        input_ports: Iterable[InputPort] = (),
        output_ports: Iterable[OutputPort] = (),
        id: uuid.UUID | None = None,
        domain: str = "",
        repo_url: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.domain_id = domain_id
        self.domain = domain
        self.status = status
        self.input_ports = tuple(input_ports)
        self.output_ports = tuple(output_ports)
        self.repo_url = repo_url
        self.created_at = created_at
        self.updated_at = updated_at
        broken = self._broken_rules()
        if broken:
            raise DataProductRuleError(broken)

    @property
    def deprecated(self) -> bool:
        return self.status in _DEPRECATED_STATUSES

    def revised(
        self,
        *,
        name: str,
        description: str,
        domain_id: uuid.UUID,
        status: str,
        input_ports: Iterable[InputPort],
        output_ports: Iterable[OutputPort],
    ) -> DataProduct:
        """The product after an edit; identity and read-only fields are kept."""
        if self.status == RETIRED_PRODUCT and status != RETIRED_PRODUCT:
            raise DataProductRuleError(["A retired data product cannot change status"])
        return DataProduct(
            name=name,
            description=description,
            domain_id=domain_id,
            status=status,
            input_ports=input_ports,
            output_ports=output_ports,
            id=self.id,
            domain=self.domain,
            repo_url=self.repo_url,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def _broken_rules(self) -> list[str]:
        broken = []
        if self.status not in PRODUCT_STATUSES:
            broken.append(f"Status must be one of: {', '.join(PRODUCT_STATUSES)}")
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
