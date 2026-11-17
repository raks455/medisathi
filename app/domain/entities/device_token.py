from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class DeviceToken:
    id: UUID
    user_id: UUID
    token: str
    platform: Optional[str] = None
    created_at: Optional[datetime] = None
