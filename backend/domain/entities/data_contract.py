import uuid
from datetime import datetime
from typing import Any

from backend.domain.contract_metadata import empty_description


class DataContract:
    def __init__(
        self,
        id: uuid.UUID,
        title: str,
        version: str,
        owner: str,
        domain: str,
        tier: int,
        status: str,
        models: dict[str, Any],
        servicelevels: dict[str, Any],
        created_at: datetime,
        updated_at: datetime,
        domain_id: uuid.UUID | None = None,
        description: dict[str, str] | None = None,
        team_members: list[dict[str, Any]] | None = None,
        support: list[dict[str, Any]] | None = None,
        servers: list[dict[str, Any]] | None = None,
    ):
        self.id = id
        self.title = title
        self.version = version
        self.owner = owner
        self.domain = domain
        self.tier = tier
        self.status = status
        self.models = models
        self.servicelevels = servicelevels
        self.created_at = created_at
        self.updated_at = updated_at
        self.domain_id = domain_id
        self.description = (
            description if description is not None else empty_description()
        )
        self.team_members = team_members if team_members is not None else []
        self.support = support if support is not None else []
        self.servers = servers if servers is not None else []
