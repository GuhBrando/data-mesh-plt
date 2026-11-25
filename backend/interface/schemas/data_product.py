"""The data product as the API carries it: ODPS ports, written together with
their product. Read-only fields (lineage, contract summary, warnings) appear only
in responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContractRefModel(BaseModel):
    """ODPS `inputContracts`: a contract version an output is built from."""

    model_config = ConfigDict(from_attributes=True)

    contract_id: uuid.UUID
    version: str = Field(min_length=1)


class AuthoritativeDefinitionModel(BaseModel):
    type: str = Field(min_length=1)
    url: str = Field(min_length=1)


class _PortModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(min_length=1)
    contract_id: uuid.UUID | None = None
    # With a contract, defaults to the contract's current version.
    version: str | None = None
    deprecated: bool = False
    authoritative_definitions: list[AuthoritativeDefinitionModel] = []


class InputPortModel(_PortModel):
    pass


class OutputPortModel(_PortModel):
    type: str | None = None
    description: str | None = None
    input_contracts: list[ContractRefModel] = []


class DataProductWriteModel(BaseModel):
    """The whole product; a PUT replaces it, ports included."""

    name: str
    description: str
    domain_id: uuid.UUID
    status: str = "draft"
    input_ports: list[InputPortModel] = []
    output_ports: list[OutputPortModel] = []


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


class DataProductResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    domain_id: uuid.UUID
    domain: str
    status: str
    deprecated: bool
    input_ports: list[InputPortResponseModel]
    output_ports: list[OutputPortResponseModel]
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
