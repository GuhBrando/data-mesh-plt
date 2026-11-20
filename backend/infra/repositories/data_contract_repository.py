from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid
    from contextlib import AbstractAsyncContextManager
    from datetime import datetime

import asyncpg

from backend.domain.contract_evolution import ContractVersionConflictError
from backend.domain.entities.contract_version import ContractVersion
from backend.domain.entities.data_contract import DataContract
from backend.domain.interfaces.data_contract_repository import IDataContractRepository

# domain name comes from the JOIN — never stored as a denormalized text column
_SELECT = """
    SELECT dc.id, dc.title, dc.version, dc.owner,
           d.name AS domain, dc.tier, dc.status,
           dc.models, dc.servicelevels, dc.domain_id,
           dc.description, dc.team_members, dc.support, dc.servers,
           dc.created_at, dc.updated_at
    FROM catalog.data_contracts dc
    JOIN catalog.domains d ON d.id = dc.domain_id
"""


def _row_to_entity(row) -> DataContract:
    return DataContract(
        id=row["id"],
        title=row["title"],
        version=row["version"],
        owner=row["owner"],
        domain=row["domain"],
        tier=row["tier"],
        status=row["status"],
        models=json.loads(row["models"]),
        servicelevels=json.loads(row["servicelevels"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        domain_id=row["domain_id"],
        description=json.loads(row["description"]),
        team_members=json.loads(row["team_members"]),
        support=json.loads(row["support"]),
        servers=json.loads(row["servers"]),
    )


class PostgresDataContractRepository(IDataContractRepository):
    def __init__(self, db):
        self.db = db

    def transaction(self) -> AbstractAsyncContextManager[Any]:
        return self.db.transaction()

    async def get_by_id_for_update(self, contract_id: uuid.UUID) -> DataContract | None:
        # OF dc: lock the contract row, not the joined domain.
        row = await self.db.fetchrow(
            f"{_SELECT} WHERE dc.id = $1 FOR UPDATE OF dc;",
            contract_id,
        )
        return _row_to_entity(row) if row else None

    async def add_version(
        self,
        contract_id: uuid.UUID,
        version: str,
        yaml_content: str,
        created_by: uuid.UUID | None,
    ) -> None:
        try:
            await self.db.execute(
                """
                INSERT INTO catalog.contract_versions
                    (contract_id, version, yaml_content, created_by)
                VALUES ($1, $2, $3, $4);
                """,
                contract_id,
                version,
                yaml_content,
                created_by,
            )
        except asyncpg.UniqueViolationError:
            raise ContractVersionConflictError(
                f"Version {version} already exists for this contract"
            ) from None

    async def add_baseline_version(
        self,
        contract_id: uuid.UUID,
        version: str,
        yaml_content: str,
        created_at: datetime,
    ) -> None:
        # DO NOTHING needs no UPDATE privilege, which the history table lacks.
        await self.db.execute(
            """
            INSERT INTO catalog.contract_versions
                (contract_id, version, yaml_content, created_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (contract_id, version) DO NOTHING;
            """,
            contract_id,
            version,
            yaml_content,
            created_at,
        )

    async def list_versions(self, contract_id: uuid.UUID) -> list[ContractVersion]:
        rows = await self.db.fetch(
            """
            SELECT contract_id, version, created_by, created_at
            FROM catalog.contract_versions
            WHERE contract_id = $1
            ORDER BY created_at DESC, version DESC;
            """,
            contract_id,
        )
        return [
            ContractVersion(
                contract_id=r["contract_id"],
                version=r["version"],
                created_by=r["created_by"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def get_version_yaml(
        self, contract_id: uuid.UUID, version: str
    ) -> str | None:
        return await self.db.fetchval(
            """
            SELECT yaml_content FROM catalog.contract_versions
            WHERE contract_id = $1 AND version = $2;
            """,
            contract_id,
            version,
        )

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
    ) -> DataContract:
        async with self.db.transaction():
            row = await self.db.fetchrow(
                """
                INSERT INTO catalog.data_contracts
                    (title, version, owner, domain_id, tier, status,
                     models, servicelevels,
                     description, team_members, support, servers)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb,
                        $9::jsonb, $10::jsonb, $11::jsonb, $12::jsonb)
                RETURNING id;
                """,
                title,
                version,
                owner,
                domain_id,
                tier,
                status,
                json.dumps(models),
                json.dumps(servicelevels),
                json.dumps(description),
                json.dumps(team_members),
                json.dumps(support),
                json.dumps(servers),
            )
            return await self.get_by_id(row["id"])

    async def get_by_id(self, contract_id: uuid.UUID) -> DataContract | None:
        row = await self.db.fetchrow(
            f"{_SELECT} WHERE dc.id = $1;",
            contract_id,
        )
        return _row_to_entity(row) if row else None

    async def list(self) -> list[DataContract]:
        rows = await self.db.fetch(f"{_SELECT} ORDER BY dc.created_at DESC;")
        return [_row_to_entity(r) for r in rows]

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
    ) -> DataContract | None:
        async with self.db.transaction():
            row = await self.db.fetchrow(
                """
                UPDATE catalog.data_contracts
                SET title = $1, version = $2, owner = $3, domain_id = $4,
                    tier = $5, status = $6,
                    models = $7::jsonb, servicelevels = $8::jsonb,
                    description = $9::jsonb, team_members = $10::jsonb,
                    support = $11::jsonb, servers = $12::jsonb,
                    updated_at = now()
                WHERE id = $13
                RETURNING id;
                """,
                title,
                version,
                owner,
                domain_id,
                tier,
                status,
                json.dumps(models),
                json.dumps(servicelevels),
                json.dumps(description),
                json.dumps(team_members),
                json.dumps(support),
                json.dumps(servers),
                contract_id,
            )
            if row is None:
                return None
            return await self.get_by_id(row["id"])

    async def delete(self, contract_id: uuid.UUID) -> bool:
        try:
            async with self.db.transaction():
                result = await self.db.execute(
                    "DELETE FROM catalog.data_contracts WHERE id = $1;",
                    contract_id,
                )
                return result == "DELETE 1"
        except asyncpg.ForeignKeyViolationError:
            raise ValueError(
                "Cannot delete this contract because it is still"
                " referenced by one or more data products."
                " Remove those references first."
            )

    async def list_by_domain_id(self, domain_id: uuid.UUID) -> list[DataContract]:
        rows = await self.db.fetch(
            f"{_SELECT} WHERE dc.domain_id = $1 ORDER BY dc.created_at DESC;",
            domain_id,
        )
        return [_row_to_entity(r) for r in rows]

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
        # One statement, so it cannot race a concurrent sync of the same file.
        # The caller knows whether the row existed from its locked read.
        await self.db.execute(
            """
            INSERT INTO catalog.data_contracts
                (id, title, version, owner, domain_id, tier, status,
                 models, servicelevels,
                 description, team_members, support, servers)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb,
                    $10::jsonb, $11::jsonb, $12::jsonb, $13::jsonb)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title, version = EXCLUDED.version,
                owner = EXCLUDED.owner, domain_id = EXCLUDED.domain_id,
                tier = EXCLUDED.tier, status = EXCLUDED.status,
                models = EXCLUDED.models, servicelevels = EXCLUDED.servicelevels,
                description = EXCLUDED.description,
                team_members = EXCLUDED.team_members,
                support = EXCLUDED.support, servers = EXCLUDED.servers,
                updated_at = now();
            """,
            contract_id,
            title,
            version,
            owner,
            domain_id,
            tier,
            status,
            json.dumps(models),
            json.dumps(servicelevels),
            json.dumps(description),
            json.dumps(team_members),
            json.dumps(support),
            json.dumps(servers),
        )
        return await self.get_by_id(contract_id)
