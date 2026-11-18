import uuid
from datetime import datetime


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
