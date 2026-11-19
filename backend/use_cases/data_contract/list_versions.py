import uuid

from backend.domain.entities.contract_version import ContractVersion
from backend.domain.interfaces.data_contract_repository import IDataContractRepository


class ListContractVersionsUseCase:
    def __init__(self, repository: IDataContractRepository):
        self.repository = repository

    async def execute(self, contract_id: uuid.UUID) -> list[ContractVersion] | None:
        """Newest first. None means the contract does not exist; [] means no history."""
        versions = await self.repository.list_versions(contract_id)
        # Every contract written since the history began has a row, so the
        # existence check runs only for an empty history.
        if versions or await self.repository.get_by_id(contract_id) is not None:
            return versions
        return None
