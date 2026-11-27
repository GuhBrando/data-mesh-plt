import uuid
from typing import Any, NamedTuple

from backend.domain.contract_evolution import (
    IN_REVIEW_STATUS,
    RETIRED_STATUS,
    ContractInReviewError,
    ContractStatusConflictError,
    RetiredContractError,
)
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
        expected_status: str | None = None,
    ) -> UpdatedContract | None:
        """Apply `changes`; a field that is absent or None keeps its stored value.

        `expected_status`: the status the caller decided from. A move lands only
        when the locked row still has it, so two reviewers never both win.
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
            if expected_status is not None and current.status != expected_status:
                raise ContractStatusConflictError(
                    f"The contract is now {current.status}. Reload and try again."
                )
            edits = {k for k, v in changes.items() if v is not None and k != "status"}
            if current.status == IN_REVIEW_STATUS and edits:
                raise ContractInReviewError(
                    "This contract is in review. Withdraw it to edit."
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
