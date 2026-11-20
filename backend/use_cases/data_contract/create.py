import uuid
from typing import Any

from backend.domain.entities.data_contract import DataContract
from backend.domain.interfaces.data_contract_repository import IDataContractRepository


class CreateDataContractUseCase:
    def __init__(self, repository: IDataContractRepository):
        self.repository = repository

    async def execute(
        self,
        title: str,
        version: str,
        owner: str,
        domain_id: uuid.UUID,
        tier: int,
        status: str,
        models: dict[str, Any],
        servicelevels: dict[str, Any],
        description: dict[str, Any],
        team_members: list[dict[str, Any]],
        support: list[dict[str, Any]],
        servers: list[dict[str, Any]],
    ) -> DataContract:
        if not title:
            raise ValueError("Data contract title cannot be empty")
        return await self.repository.create(
            title=title,
            version=version,
            owner=owner,
            domain_id=domain_id,
            tier=tier,
            status=status,
            models=models,
            servicelevels=servicelevels,
            description=description,
            team_members=team_members,
            support=support,
            servers=servers,
        )
