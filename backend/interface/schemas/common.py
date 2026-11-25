"""Row models the contract (ODCS) and the data product (ODPS) share. ODPS takes
team, support, custom properties and authoritative definitions from ODCS, so both
APIs validate them with these models, never with copies."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from backend.domain.contract_metadata import support_url_problem

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
# The nested rows forbid unknown keys, like the ODCS reader: a key the platform
# does not model must fail loudly instead of being dropped.
STRICT = ConfigDict(extra="forbid")


class TeamMember(BaseModel):
    model_config = STRICT

    username: NonEmptyStr
    name: str = ""
    role: str = ""


class SupportChannel(BaseModel):
    model_config = STRICT

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


class CustomProperty(BaseModel):
    """ODPS and ODCS `customProperties[]`: the value may be of any JSON type."""

    model_config = STRICT

    property: NonEmptyStr
    value: Any
    description: str | None = None
    vendor: str | None = None
    id: str | None = None


class AuthoritativeDefinition(BaseModel):
    model_config = STRICT

    type: NonEmptyStr
    url: NonEmptyStr
    description: str | None = None
    id: str | None = None
