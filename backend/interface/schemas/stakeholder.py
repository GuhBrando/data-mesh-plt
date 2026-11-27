import uuid
from datetime import datetime

from pydantic import BaseModel


class StakeholderAssignModel(BaseModel):
    user_id: uuid.UUID


class StakeholderViewModel(BaseModel):
    user_id: uuid.UUID
    username: str
    role: str
    assigned_by_username: str
    assigned_at: datetime


class StakeholderResponseModel(BaseModel):
    contract_id: uuid.UUID
    user_id: uuid.UUID
    assigned_by: uuid.UUID | None
    assigned_at: datetime
