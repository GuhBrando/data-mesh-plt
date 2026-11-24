from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    import uuid
    from contextlib import AbstractAsyncContextManager

    from backend.domain.entities.data_product import DataProduct, PortUsage


class LegacyProduct(NamedTuple):
    """A product still linked to one contract by `data_contracts_id`, before the
    backfill gives it an output port. Deleted with that column in ODPS plan 2."""

    id: uuid.UUID
    name: str
    description: str
    domain_id: uuid.UUID
    status: str
    contract_id: uuid.UUID


class IDataProductRepository(ABC):
    """Stores the DataProduct aggregate with its ports. Every constraint
    violation on a write surfaces as DataProductRuleError."""

    @abstractmethod
    def transaction(self) -> AbstractAsyncContextManager[Any]:
        """One transaction for a whole use case; nested writes become savepoints."""

    @abstractmethod
    async def add(self, product: DataProduct) -> DataProduct:
        """Insert the product and its ports; return it as stored."""

    @abstractmethod
    async def replace(self, product: DataProduct) -> DataProduct | None:
        """Overwrite the product and replace its ports, matched by role, name and
        version so they keep their ids. None when the product does not exist."""

    @abstractmethod
    async def get_by_id(self, product_id: uuid.UUID) -> DataProduct | None: ...

    @abstractmethod
    async def list(self) -> list[DataProduct]:
        """Every product, most recently updated first."""

    @abstractmethod
    async def delete(self, product_id: uuid.UUID) -> bool: ...

    @abstractmethod
    async def update_repo_url(self, product_id: uuid.UUID, repo_url: str) -> None: ...

    @abstractmethod
    async def list_port_usage(self, contract_ids: list[uuid.UUID]) -> list[PortUsage]:
        """Every port that references one of `contract_ids`, outputs first."""

    @abstractmethod
    async def list_legacy_products(self) -> list[LegacyProduct]: ...
