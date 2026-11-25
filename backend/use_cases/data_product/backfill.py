"""Gives every product created before ODPS its output port (ODPS plan 1).

Run by entrypoint.sh after the migrations and before the app serves, so no
request reads a product without an output. Idempotent: a migrated product no
longer has `data_contracts_id`, so a second run finds nothing. ODPS plan 2
deletes this module with that column.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.data_product import DataProduct, OutputPort
from backend.domain.naming import slugify
from backend.use_cases.data_contract.versioning import baseline

if TYPE_CHECKING:
    from backend.domain.interfaces.data_contract_repository import (
        IDataContractRepository,
    )
    from backend.domain.interfaces.data_product_repository import (
        IDataProductRepository,
    )


class BackfillOutputPortsUseCase:
    def __init__(
        self, products: IDataProductRepository, contracts: IDataContractRepository
    ):
        self.products = products
        self.contracts = contracts

    async def execute(self) -> int:
        """Migrate each linked product in its own transaction; return how many."""
        legacy = await self.products.list_legacy_products()
        for item in legacy:
            async with self.products.transaction():
                # The old foreign key kept the contract alive, so it exists.
                contract = await self.contracts.get_by_id(item.contract_id)
                await self.contracts.add_baseline_versions([baseline(contract)])
                port = OutputPort(
                    name=slugify(contract.title) or "output",
                    contract_id=contract.id,
                    version=contract.version,
                    type="tables",
                )
                await self.products.replace(
                    DataProduct(
                        id=item.id,
                        name=item.name,
                        description=item.description,
                        domain_id=item.domain_id,
                        status=item.status,
                        output_ports=[port],
                    )
                )
        return len(legacy)
