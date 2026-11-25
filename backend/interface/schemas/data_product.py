"""The data product as the API carries it, faithful to ODPS v1.1.0 field by field
(snake_case here, camelCase in the ODPS export). Ports are written together with
their product. Read-only fields (lineage, contract summary, warnings) appear only
in responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.domain.contract_metadata import support_url_problem
from backend.interface.schemas.common import (
    STRICT,
    AuthoritativeDefinition,
    CustomProperty,
    NonEmptyStr,
    SupportChannel,
    TeamMember,
)

__all__ = ["AuthoritativeDefinition", "CustomProperty"]


class _Annotated(BaseModel):
    """The three lists ODPS attaches to most of its objects."""

    model_config = STRICT

    tags: list[str] = []
    custom_properties: list[CustomProperty] = []
    authoritative_definitions: list[AuthoritativeDefinition] = []


class ProductTeamMember(TeamMember, _Annotated):
    id: str | None = None
    description: str | None = None
    date_in: str | None = None
    date_out: str | None = None
    replaced_by_username: str | None = None


class ProductSupportChannel(SupportChannel, _Annotated):
    """ODPS requires the URL, which may be an unresolved `${VAR}`."""

    url: NonEmptyStr
    id: str | None = None
    description: str | None = None
    invitation_url: str | None = None

    @field_validator("url")
    @classmethod
    def _linkable(cls, url: str) -> str:
        problem = support_url_problem(url, allow_variables=True)
        if problem:
            raise ValueError(problem)
        return url


class Team(_Annotated):
    id: str | None = None
    name: str | None = None
    description: str | None = None
    members: list[ProductTeamMember] = []


class Synonym(BaseModel):
    model_config = STRICT

    synonym: NonEmptyStr
    id: str | None = None
    description: str | None = None
    locale: str | None = None
    source: str | None = None
    status: str | None = None
    custom_properties: list[CustomProperty] = []


class VerifiedStatement(_Annotated):
    question: NonEmptyStr
    answer: str | None = None
    id: str | None = None


class ContextConstraint(_Annotated):
    constraint: NonEmptyStr
    id: str | None = None


class Context(BaseModel):
    """Guidance for AI agents and tools (ODPS RFC-0038)."""

    model_config = STRICT

    instructions: str | None = None
    verified_statements: list[VerifiedStatement] = []
    constraints: list[ContextConstraint] = []


class Sbom(_Annotated):
    id: str | None = None
    type: str | None = None
    url: str | None = None


class ProductDescription(BaseModel):
    model_config = STRICT

    purpose: str = ""
    usage: str = ""
    limitations: str = ""
    authoritative_definitions: list[AuthoritativeDefinition] = []
    custom_properties: list[CustomProperty] = []


class ContractRefModel(BaseModel):
    """ODPS `inputContracts`: a contract version an output is built from."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    contract_id: uuid.UUID
    version: str = Field(min_length=1)


class _PortModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    name: str = Field(min_length=1)
    contract_id: uuid.UUID | None = None
    # With a contract, defaults to the contract's current version.
    version: str | None = None
    deprecated: bool = False
    tags: list[str] = []
    custom_properties: list[CustomProperty] = []
    authoritative_definitions: list[AuthoritativeDefinition] = []


class InputPortModel(_PortModel):
    pass


class OutputPortModel(_PortModel):
    type: str | None = None
    description: str | None = None
    input_contracts: list[ContractRefModel] = []
    synonyms: list[Synonym] = []
    context: Context = Context()
    sbom: list[Sbom] = []


class ManagementPortModel(_Annotated):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    name: NonEmptyStr
    content: NonEmptyStr
    # Checked by the database: rest or topic.
    type: str = "rest"
    url: str | None = None
    channel: str | None = None
    description: str | None = None
    deprecated: bool = False


class DataProductWriteModel(BaseModel):
    """The whole product; a PUT replaces it, ports included."""

    name: str
    description: ProductDescription = ProductDescription()
    domain_id: uuid.UUID
    status: str = "draft"
    version: str | None = None
    type: str | None = None
    tenant: str | None = None
    tags: list[str] = []
    synonyms: list[Synonym] = []
    context: Context = Context()
    team: Team = Team()
    support: list[ProductSupportChannel] = []
    custom_properties: list[CustomProperty] = []
    authoritative_definitions: list[AuthoritativeDefinition] = []
    input_ports: list[InputPortModel] = []
    output_ports: list[OutputPortModel] = []
    management_ports: list[ManagementPortModel] = []


class ContractSummaryModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    status: str
    version: str
    domain: str


class ProductRefModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: str


class InputPortResponseModel(InputPortModel):
    id: uuid.UUID
    contract: ContractSummaryModel | None = None
    produced_by: list[ProductRefModel] = []


class OutputPortResponseModel(OutputPortModel):
    id: uuid.UUID
    contract: ContractSummaryModel | None = None
    consumed_by: list[ProductRefModel] = []


class ManagementPortResponseModel(ManagementPortModel):
    id: uuid.UUID


class DataProductResponseModel(DataProductWriteModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    domain: str
    deprecated: bool
    input_ports: list[InputPortResponseModel]
    output_ports: list[OutputPortResponseModel]
    management_ports: list[ManagementPortResponseModel] = []
    repo_url: str | None = None
    created_at: datetime
    updated_at: datetime
    warnings: list[str] = []


class PortUsageResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    product_name: str
    domain: str
    status: str
    role: str
    port_name: str
    version: str
