import uuid
from datetime import datetime
from typing import NamedTuple


class ContractVersion:
    """One immutable history row. The YAML is read separately, on demand."""

    def __init__(
        self,
        contract_id: uuid.UUID,
        version: str,
        created_by: uuid.UUID | None,
        created_at: datetime,
    ):
        self.contract_id = contract_id
        self.version = version
        self.created_by = created_by
        self.created_at = created_at


class ContractBaseline(NamedTuple):
    """The version a contract had before its history began, to record if absent."""

    contract_id: uuid.UUID
    version: str
    yaml_content: str
    created_at: datetime
