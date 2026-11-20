import uuid

from backend.domain.interfaces.data_contract_repository import IDataContractRepository


class GetContractVersionYamlUseCase:
    def __init__(self, repository: IDataContractRepository):
        self.repository = repository

    async def execute(self, contract_id: uuid.UUID, version: str) -> str | None:
        return await self.repository.get_version_yaml(contract_id, version)
