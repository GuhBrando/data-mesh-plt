import uuid

from backend.domain.entities.contract_stakeholder import ContractStakeholder
from backend.domain.interfaces.stakeholder_repository import IStakeholderRepository


class PostgresStakeholderRepository(IStakeholderRepository):
    def __init__(self, db):
        self.db = db

    async def assign(
        self, contract_id: uuid.UUID, user_id: uuid.UUID, assigned_by: uuid.UUID
    ) -> ContractStakeholder:
        async with self.db.transaction():
            row = await self.db.fetchrow(
                """
                INSERT INTO catalog.contract_stakeholders
                  (contract_id, user_id, assigned_by)
                VALUES ($1, $2, $3)
                ON CONFLICT (contract_id, user_id)
                DO UPDATE SET assigned_by = EXCLUDED.assigned_by
                RETURNING contract_id, user_id, assigned_by, assigned_at;
                """,
                contract_id,
                user_id,
                assigned_by,
            )
            return ContractStakeholder(
                contract_id=row["contract_id"],
                user_id=row["user_id"],
                assigned_by=row["assigned_by"],
                assigned_at=row["assigned_at"],
            )

    async def remove(self, contract_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            """
            DELETE FROM catalog.contract_stakeholders
            WHERE contract_id = $1 AND user_id = $2;
            """,
            contract_id,
            user_id,
        )
        return result == "DELETE 1"

    async def is_stakeholder(self, contract_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        row = await self.db.fetchrow(
            """
            SELECT 1 FROM catalog.contract_stakeholders
            WHERE contract_id = $1 AND user_id = $2;
            """,
            contract_id,
            user_id,
        )
        return row is not None

    async def contract_ids_of(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        rows = await self.db.fetch(
            """
            SELECT contract_id FROM catalog.contract_stakeholders
            WHERE user_id = $1;
            """,
            user_id,
        )
        return {row["contract_id"] for row in rows}
