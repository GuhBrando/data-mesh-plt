import uuid
from typing import Callable

from fastapi import Depends, HTTPException

from backend.domain.entities.user import User
from backend.domain.value_objects.user_role import UserRole
from backend.interface.security import get_current_user


def require_roles(*roles: UserRole) -> Callable:
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return dependency


async def member_domain_ids(user_id: uuid.UUID, db) -> set[uuid.UUID]:
    """Every domain the user is a member of, in one query."""
    rows = await db.fetch(
        "SELECT domain_id FROM catalog.domain_members WHERE user_id = $1;",
        user_id,
    )
    return {row["domain_id"] for row in rows}


async def is_domain_member(user_id: uuid.UUID, domain_id: uuid.UUID, db) -> bool:
    row = await db.fetchrow(
        """
        SELECT 1 FROM catalog.domain_members
        WHERE user_id = $1 AND domain_id = $2;
        """,
        user_id,
        domain_id,
    )
    return row is not None
