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

from backend.domain.contract_metadata import server_problems
from backend.domain.quality_rules import find_quality_rule_problems

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


def _reject_bool(value: Any) -> Any:
    # Pydantic's lax mode would store True as the number 1.
    if isinstance(value, bool):
        raise ValueError("must be a number, not a boolean")
    return value


class QualityRule(BaseModel):
    """An ODCS quality rule: a library metric the tool can run, or text."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["library", "text"]
    dimension: (
        Literal[
            "accuracy",
            "completeness",
            "conformity",
            "consistency",
            "coverage",
            "timeliness",
            "uniqueness",
        ]
        | None
    ) = None
    column: str = ""
    metric: (
        Literal[
            "nullValues",
            "missingValues",
            "invalidValues",
            "duplicateValues",
            "rowCount",
        ]
        | None
    ) = None
    operator: (
        Literal[
            "mustBe",
            "mustNotBe",
            "mustBeGreaterThan",
            "mustBeGreaterOrEqualTo",
            "mustBeLessThan",
            "mustBeLessOrEqualTo",
        ]
        | None
    ) = None
    value: int | float | None = None
    unit: Literal["rows", "percent"] | None = None
    valid_values: list[str] = []
    description: str = ""

    _no_bool_value = field_validator("value", mode="before")(_reject_bool)


class ModelsSection(BaseModel):
    fields: list[SchemaField] = []
    quality: list[QualityRule] = []

    @model_validator(mode="after")
    def _rules_can_run(self) -> "ModelsSection":
        rules = [r.model_dump() for r in self.quality]
        fields = [f.model_dump() for f in self.fields]
        problems = find_quality_rule_problems(rules, fields)
        if problems:
            raise ValueError("; ".join(problems))
        return self


class ServiceLevelProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property: str = Field(min_length=1)
    value: int | float | str
    unit: str | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _storable(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            raise ValueError("a text value cannot be blank")
        return _reject_bool(value)


class ServiceLevels(BaseModel):
    # forbid: a stale client sending the old four keys gets 422, not an empty SLA.
    model_config = ConfigDict(extra="forbid")

    properties: list[ServiceLevelProperty] = []


class ContractDescription(BaseModel):
    purpose: str = ""
    usage: str = ""
    limitations: str = ""


class TeamMember(BaseModel):
    username: NonEmptyStr
    name: str = ""
    role: str = ""


class SupportChannel(BaseModel):
    channel: NonEmptyStr
    url: str = ""
    tool: str = ""
    scope: str = ""


class ContractServer(BaseModel):
    """Where the data lives. Coordinates only: no credential belongs here."""

    model_config = ConfigDict(extra="forbid")

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
    # retired is reachable only by an update: a contract is not born retired.
    status: Literal["draft", "in_review", "active", "deprecated", "retired"] | None = (
        None
    )
    models: ModelsSection | None = None
    servicelevels: ServiceLevels | None = None
    description: ContractDescription | None = None
    team_members: list[TeamMember] | None = None
    support: list[SupportChannel] | None = None
    servers: list[ContractServer] | None = None


class ContractVersionResponseModel(BaseModel):
    version: str
    created_by: uuid.UUID | None
    created_at: datetime


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
