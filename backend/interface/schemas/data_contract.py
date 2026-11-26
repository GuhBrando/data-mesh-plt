import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.domain.contract_metadata import server_problems
from backend.domain.quality_rules import find_quality_rule_problems
from backend.domain.service_levels import service_level_problems
from backend.interface.schemas.common import (
    STRICT,
    NonEmptyStr,
    SupportChannel,
    TeamMember,
)

__all__ = ["NonEmptyStr", "SupportChannel", "TeamMember"]


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

    model_config = STRICT

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
    model_config = STRICT

    property: str = Field(min_length=1)
    value: int | float | str
    unit: str | None = None

    _no_bool_value = field_validator("value", mode="before")(_reject_bool)


class ServiceLevels(BaseModel):
    # forbid: a stale client sending the old four keys gets 422, not an empty SLA.
    model_config = STRICT

    properties: list[ServiceLevelProperty] = []

    @model_validator(mode="after")
    def _storable(self) -> "ServiceLevels":
        # The rules the file readers apply: what is saved here can sync back.
        problems = service_level_problems([p.model_dump() for p in self.properties])
        if problems:
            raise ValueError("; ".join(problems))
        return self


class ContractDescription(BaseModel):
    model_config = STRICT

    purpose: str = ""
    usage: str = ""
    limitations: str = ""


class ContractServer(BaseModel):
    """Where the data lives. Coordinates only: no credential belongs here."""

    model_config = STRICT

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
    # Every contract is born a draft; it moves on with POST .../status.
    status: Literal["draft"] = "draft"
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
    # Declared only to refuse it: the status moves with POST .../status, which
    # checks who may make the move.
    status: Any = None
    models: ModelsSection | None = None
    servicelevels: ServiceLevels | None = None
    description: ContractDescription | None = None
    team_members: list[TeamMember] | None = None
    support: list[SupportChannel] | None = None
    servers: list[ContractServer] | None = None

    @field_validator("status")
    @classmethod
    def _status_has_its_own_endpoint(cls, value: Any) -> None:
        if value is not None:
            raise ValueError("Change the status with POST /data-contracts/{id}/status")
        return


class ContractStatusChangeModel(BaseModel):
    status: Literal["draft", "in_review", "active", "deprecated", "retired"]


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
