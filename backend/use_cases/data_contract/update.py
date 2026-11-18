import uuid
from typing import Any

from backend.domain.contract_evolution import RETIRED_STATUS, RetiredContractError
from backend.domain.entities.data_contract import DataContract
from backend.domain.interfaces.data_contract_repository import IDataContractRepository
from backend.use_cases.data_contract.versioning import (
    enforce_evolution,
    record_version,
    validate_new_version,
)


class UpdateDataContractUseCase:
    def __init__(self, repository: IDataContractRepository):
        self.repository = repository

    async def execute(
        self,
        contract_id: uuid.UUID,
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
        created_by: uuid.UUID | None = None,
    ) -> DataContract | None:
        if not title:
            raise ValueError("Data contract title cannot be empty")
        # Lock, write, check and snapshot in one transaction, so a rejected
        # change rolls back and two concurrent bumps cannot reorder versions.
        async with self.repository.transaction():
            current = await self.repository.get_by_id_for_update(contract_id)
            if current is None:
                return None
            if current.status == RETIRED_STATUS:
                raise RetiredContractError(
                    f"Contract {contract_id} is retired and cannot be changed"
                )
            validate_new_version(version, current)
            updated = await self.repository.update(
                contract_id=contract_id,
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
            if updated is None:
                return None
            # Checked after the write: to_odcs needs the joined domain name,
            # and the update may have moved the contract to another domain.
            enforce_evolution(current, updated)
            await record_version(self.repository, current, updated, created_by)
        return updated
