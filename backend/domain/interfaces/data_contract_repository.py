from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid
    from contextlib import AbstractAsyncContextManager

    from backend.domain.entities.contract_version import (
        ContractBaseline,
        ContractVersion,
    )
    from backend.domain.entities.data_contract import DataContract


class IDataContractRepository(ABC):
    @abstractmethod
    def transaction(self) -> AbstractAsyncContextManager[Any]:
        """One transaction for a whole use case; nested writes become savepoints."""

    @abstractmethod
    async def get_by_id_for_update(self, contract_id: uuid.UUID) -> DataContract | None:
        """Read the contract and lock its row until the transaction ends."""

    @abstractmethod
    async def add_version(
        self,
        contract_id: uuid.UUID,
        version: str,
        yaml_content: str,
        created_by: uuid.UUID | None,
    ) -> None: ...

    @abstractmethod
    async def add_baseline_versions(self, baselines: list[ContractBaseline]) -> None:
        """Record each version a contract had before its history began, if absent."""

    @abstractmethod
    async def list_by_ids(self, contract_ids: list[uuid.UUID]) -> list[DataContract]:
        """The contracts among `contract_ids` that exist, in one query."""

    @abstractmethod
    async def list_versions(self, contract_id: uuid.UUID) -> list[ContractVersion]: ...

    @abstractmethod
    async def get_version_yaml(
        self, contract_id: uuid.UUID, version: str
    ) -> str | None: ...

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
    ) -> DataContract:
        """Insert or update a contract by id and return it as stored."""
