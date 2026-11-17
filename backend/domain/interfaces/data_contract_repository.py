from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid

    from backend.domain.entities.data_contract import DataContract


class IDataContractRepository(ABC):
    @abstractmethod
    async def create(
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
    ) -> DataContract: ...

    @abstractmethod
    async def get_by_id(self, contract_id: uuid.UUID) -> DataContract | None: ...

    @abstractmethod
    async def list(self) -> list[DataContract]: ...

    @abstractmethod
    async def update(
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
    ) -> DataContract | None: ...

    @abstractmethod
    async def delete(self, contract_id: uuid.UUID) -> bool: ...

    @abstractmethod
    async def list_by_domain_id(self, domain_id: uuid.UUID) -> list[DataContract]: ...

    @abstractmethod
    async def upsert(
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
    ) -> bool:
        """Insert or update a contract by id.

        Returns True if created, False if updated.
        """
        ...
