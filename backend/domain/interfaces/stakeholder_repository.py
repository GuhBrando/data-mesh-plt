import uuid
from abc import ABC, abstractmethod

from backend.domain.entities.contract_stakeholder import ContractStakeholder


class IStakeholderRepository(ABC):
    @abstractmethod
    async def assign(
        self, contract_id: uuid.UUID, user_id: uuid.UUID, assigned_by: uuid.UUID
    ) -> ContractStakeholder: ...

    @abstractmethod
    async def remove(self, contract_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    @abstractmethod
    async def is_stakeholder(
        self, contract_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool: ...

    @abstractmethod
    async def contract_ids_of(self, user_id: uuid.UUID) -> set[uuid.UUID]: ...
