import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StakeholderView:
    """A person invited to review a draft contract, named for the page."""

    user_id: uuid.UUID
    username: str
    role: str  # the person's platform role
    assigned_by_username: str  # "" when the inviter's account is gone
    assigned_at: datetime
