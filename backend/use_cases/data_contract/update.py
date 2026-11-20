import uuid
from typing import Any, NamedTuple

from backend.domain.contract_evolution import RETIRED_STATUS, RetiredContractError
from backend.domain.entities.data_contract import CONTRACT_VALUE_FIELDS, DataContract
from backend.domain.interfaces.data_contract_repository import IDataContractRepository
from backend.use_cases.data_contract.versioning import (
    apply_evolution,
    validate_new_version,
)

_UPDATABLE_FIELDS = ("domain_id", *CONTRACT_VALUE_FIELDS)


class UpdatedContract(NamedTuple):
    previous: DataContract
    current: DataContract


class UpdateDataContractUseCase:
    def __init__(self, repository: IDataContractRepository):
        self.repository = repository

    async def execute(
        self,
        contract_id: uuid.UUID,
        changes: dict[str, Any],
        created_by: uuid.UUID | None = None,
    ) -> UpdatedContract | None:
        """Apply `changes`; a field that is absent or None keeps its stored value.

        None when the contract does not exist.
        """
        # Lock, merge, write, check and snapshot in one transaction: the merge
        # reads the locked row, so a concurrent update is never overwritten with
        # stale values, and a rejected change rolls back.
        async with self.repository.transaction():
            current = await self.repository.get_by_id_for_update(contract_id)
            if current is None:
                return None
            if current.status == RETIRED_STATUS:
                raise RetiredContractError(
                    f"Contract {contract_id} is retired and cannot be changed"
                )
            fields = {name: getattr(current, name) for name in _UPDATABLE_FIELDS}
            fields.update((k, v) for k, v in changes.items() if v is not None)
            if not fields["title"]:
                raise ValueError("Data contract title cannot be empty")
            validate_new_version(fields["version"], current)
            updated = await self.repository.update(contract_id=contract_id, **fields)
            if updated is None:
                return None
            # Checked after the write: to_odcs needs the joined domain name,
            # and the update may have moved the contract to another domain.
            await apply_evolution(self.repository, current, updated, created_by)
        return UpdatedContract(current, updated)
