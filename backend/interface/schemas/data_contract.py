import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from backend.domain.contract_metadata import server_problems, support_url_problem

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SchemaField(BaseModel):
    name: str
    type: Literal["string", "integer", "float", "boolean", "date", "timestamp"]
    description: str = ""
    nullable: bool = True
    primary_key: bool = False
    classification: Literal["", "public", "internal", "confidential", "restricted"] = ""
    unique: bool = False
    physical_type: str = ""


class QualityRule(BaseModel):
    dimension: Literal[
        "completeness", "freshness", "uniqueness", "validity", "integrity"
    ]
    column: str = ""
    operator: Literal[">=", "<=", "="]
    threshold: str
    description: str = ""


class ModelsSection(BaseModel):
    fields: list[SchemaField] = []
    quality: list[QualityRule] = []


class ServiceLevels(BaseModel):
    freshness: str = ""
    availability: str = ""
    retention: str = ""
    latency: str = ""


# The metadata rows forbid unknown keys, like the ODCS reader: a key the
# platform does not model must fail loudly instead of being dropped.
_STRICT = ConfigDict(extra="forbid")


class ContractDescription(BaseModel):
    model_config = _STRICT

    purpose: str = ""
    usage: str = ""
    limitations: str = ""


class TeamMember(BaseModel):
    model_config = _STRICT

    username: NonEmptyStr
    name: str = ""
    role: str = ""


class SupportChannel(BaseModel):
    model_config = _STRICT

    channel: NonEmptyStr
    url: str = ""
    tool: str = ""
    scope: str = ""

    @field_validator("url")
    @classmethod
    def _linkable(cls, url: str) -> str:
        problem = support_url_problem(url)
        if problem:
            raise ValueError(problem)
        return url


class ContractServer(BaseModel):
    """Where the data lives. Coordinates only: no credential belongs here."""

    model_config = _STRICT

    server: NonEmptyStr
    type: Literal["databricks", "postgres", "azure", "local"]
    environment: str = ""
    host: str = ""
    catalog: str = ""
    schema_name: str = ""
    port: int | None = None
    database: str = ""
    location: str = ""
    format: str = ""
    path: str = ""

    @model_validator(mode="after")
    def _follow_the_type_rules(self) -> "ContractServer":
        problems = server_problems(self.model_dump())
        if problems:
            raise ValueError("; ".join(problems))
        return self


class DataContractCreateModel(BaseModel):
    title: str
    version: str = "1.0.0"
    owner: str
    domain_id: uuid.UUID
    tier: int = Field(..., ge=1, le=4)
    status: Literal["draft", "in_review", "active", "deprecated"] = "draft"
    models: ModelsSection = Field(default_factory=ModelsSection)
    servicelevels: ServiceLevels = Field(default_factory=ServiceLevels)
    description: ContractDescription = Field(default_factory=ContractDescription)
    team_members: list[TeamMember] = Field(default_factory=list)
    support: list[SupportChannel] = Field(default_factory=list)
    servers: list[ContractServer] = Field(default_factory=list)


class DataContractUpdateModel(BaseModel):
    title: str | None = None
    version: str | None = None
    owner: str | None = None
    domain_id: uuid.UUID | None = None
    tier: int | None = Field(default=None, ge=1, le=4)
    status: Literal["draft", "in_review", "active", "deprecated"] | None = None
    models: ModelsSection | None = None
    servicelevels: ServiceLevels | None = None
    description: ContractDescription | None = None
    team_members: list[TeamMember] | None = None
    support: list[SupportChannel] | None = None
    servers: list[ContractServer] | None = None


class DataContractResponseModel(BaseModel):
    id: uuid.UUID
    title: str
    version: str
    owner: str
    domain: str  # joined name — read-only, never sent by client
    tier: int
    status: str
    models: dict[str, Any]
    servicelevels: dict[str, Any]
    # Loose shapes, like models: an old stored row must not turn a read into a 500.
    description: dict[str, Any]
    team_members: list[dict[str, Any]]
    support: list[dict[str, Any]]
    servers: list[dict[str, Any]]
    domain_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
