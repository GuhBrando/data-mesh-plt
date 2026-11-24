from __future__ import annotations

import json
import uuid

import asyncpg

from backend.domain.entities.domain import Domain, DomainMember
from backend.domain.interfaces.domain_repository import IDomainRepository

_RICH_SELECT = """
    SELECT
        d.id,
        d.name,
        d.description,
        d.owner_id,
        COALESCE(ou.name, '')      AS owner_username,
        d.created_at,
        d.updated_at,
        COUNT(DISTINCT dc.id)::int AS contract_count,
        COALESCE(
            json_agg(
                json_build_object(
                    'user_id',  dm.user_id,
                    'username', mu.name,
                    'role',     dm.role
                )
                ORDER BY mu.name
            ) FILTER (WHERE dm.user_id IS NOT NULL),
            '[]'::json
        ) AS members
    FROM catalog.domains d
    LEFT JOIN iam.users ou        ON ou.id = d.owner_id
    LEFT JOIN catalog.domain_members dm ON dm.domain_id = d.id
    LEFT JOIN iam.users mu        ON mu.id = dm.user_id
    LEFT JOIN catalog.data_contracts dc ON dc.domain_id = d.id
"""


def _row_to_domain(row) -> Domain:
    raw = row["members"]
    members_data = json.loads(raw) if isinstance(raw, str) else raw or []
    members = [
        DomainMember(
            user_id=uuid.UUID(str(m["user_id"])),
            username=m["username"],
            role=m["role"],
        )
        for m in members_data
    ]
    return Domain(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        owner_id=row["owner_id"],
        owner_username=row["owner_username"] or "",
        members=members,
        contract_count=row["contract_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresDomainRepository(IDomainRepository):
    def __init__(self, db):
        self.db = db

    async def create(
        self, name: str, description: str, owner_id: uuid.UUID | None
    ) -> Domain:
        async with self.db.transaction():
            row = await self.db.fetchrow(
                """
                INSERT INTO catalog.domains (name, description, owner_id)
                VALUES ($1, $2, $3)
                RETURNING id;
                """,
                name,
                description,
                owner_id,
            )
            return await self._get_rich(row["id"])

    async def get_by_id(self, domain_id: uuid.UUID) -> Domain | None:
        return await self._get_rich(domain_id)

    async def find_by_name(self, name: str) -> Domain | None:
        row = await self.db.fetchrow(
            "SELECT id FROM catalog.domains WHERE name = $1;",
            name,
        )
        if row is None:
            return None
        return await self._get_rich(row["id"])

    async def list(self) -> list[Domain]:
        query = (
            _RICH_SELECT
            + " GROUP BY d.id, d.name, d.description, d.owner_id,"
            + " ou.name, d.created_at, d.updated_at ORDER BY d.name;"
        )
        rows = await self.db.fetch(query)
        return [_row_to_domain(r) for r in rows]

    async def update(
        self,
        domain_id: uuid.UUID,
        name: str | None,
        description: str | None,
        owner_id: uuid.UUID | None,
    ) -> Domain | None:
        existing = await self.db.fetchrow(
            "SELECT id FROM catalog.domains WHERE id = $1;",
            domain_id,
        )
        if not existing:
            return None
        if name is not None:
            await self.db.execute(
                "UPDATE catalog.domains"
                " SET name = $1, updated_at = now() WHERE id = $2;",
                name,
                domain_id,
            )
        if description is not None:
            await self.db.execute(
                "UPDATE catalog.domains"
                " SET description = $1, updated_at = now() WHERE id = $2;",
                description,
                domain_id,
            )
        if owner_id is not None:
            await self.db.execute(
                "UPDATE catalog.domains"
                " SET owner_id = $1, updated_at = now() WHERE id = $2;",
                owner_id,
                domain_id,
            )
        return await self._get_rich(domain_id)

    async def delete(self, domain_id: uuid.UUID) -> bool:
        try:
            result = await self.db.execute(
                "DELETE FROM catalog.domains WHERE id = $1;",
                domain_id,
            )
            return result != "DELETE 0"
        except asyncpg.ForeignKeyViolationError:
            raise ValueError(
                "Cannot delete this domain because data contracts or data"
                " products still use it. Move or remove them first."
            ) from None

    async def add_member(
        self, domain_id: uuid.UUID, user_id: uuid.UUID, role: str
    ) -> DomainMember:
        await self.db.execute(
            """
            INSERT INTO catalog.domain_members (domain_id, user_id, role)
            VALUES ($1, $2, $3)
            ON CONFLICT (domain_id, user_id) DO UPDATE SET role = EXCLUDED.role;
            """,
            domain_id,
            user_id,
            role,
        )
        row = await self.db.fetchrow(
            "SELECT name FROM iam.users WHERE id = $1;",
            user_id,
        )
        return DomainMember(
            user_id=user_id, username=row["name"] if row else "", role=role
        )

    async def update_member_role(
        self, domain_id: uuid.UUID, user_id: uuid.UUID, role: str
    ) -> DomainMember | None:
        result = await self.db.execute(
            """
            UPDATE catalog.domain_members
            SET role = $1
            WHERE domain_id = $2 AND user_id = $3;
            """,
            role,
            domain_id,
            user_id,
        )
        if result == "UPDATE 0":
            return None
        row = await self.db.fetchrow(
            "SELECT name FROM iam.users WHERE id = $1;",
            user_id,
        )
        return DomainMember(
            user_id=user_id, username=row["name"] if row else "", role=role
        )

    async def remove_member(self, domain_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.db.execute(
            "DELETE FROM catalog.domain_members WHERE domain_id = $1 AND user_id = $2;",
            domain_id,
            user_id,
        )

    async def is_member(self, domain_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        row = await self.db.fetchrow(
            "SELECT 1 FROM catalog.domain_members"
            " WHERE domain_id = $1 AND user_id = $2;",
            domain_id,
            user_id,
        )
        return row is not None

    async def _get_rich(self, domain_id: uuid.UUID) -> Domain | None:
        query = (
            _RICH_SELECT
            + " WHERE d.id = $1"
            + " GROUP BY d.id, d.name, d.description, d.owner_id,"
            + " ou.name, d.created_at, d.updated_at;"
        )
        row = await self.db.fetchrow(query, domain_id)
        return _row_to_domain(row) if row else None
