import uuid

from backend.domain.entities.contract_version import ContractVersion
from backend.domain.interfaces.data_contract_repository import IDataContractRepository


class ListContractVersionsUseCase:
    def __init__(self, repository: IDataContractRepository):
        self.repository = repository

    async def execute(self, contract_id: uuid.UUID) -> list[ContractVersion] | None:
        """Newest first. None means the contract does not exist; [] means no history."""
        if await self.repository.get_by_id(contract_id) is None:
            return None
        return await self.repository.list_versions(contract_id)
