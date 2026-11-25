from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from backend.domain.entities.data_product import PortUsage
    from backend.domain.interfaces.data_contract_repository import (
        IDataContractRepository,
    )
    from backend.domain.interfaces.data_product_repository import (
        IDataProductRepository,
    )


class ListContractPortsUseCase:
    """Who produces and who consumes a contract: every port that references it."""

    def __init__(
        self, products: IDataProductRepository, contracts: IDataContractRepository
    ):
        self.products = products
        self.contracts = contracts

    async def execute(self, contract_id: uuid.UUID) -> list[PortUsage] | None:
        """Outputs first. None means the contract does not exist; [] means unused."""
        usage = await self.products.list_port_usage([contract_id])
        # A used contract exists: the existence check runs only when unused.
        if usage or await self.contracts.get_by_id(contract_id) is not None:
            return usage
        return None
