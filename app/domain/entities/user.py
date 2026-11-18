from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

@dataclass
class User:
    id: UUID
    email: str
    full_name: str
    hashed_password: str
    is_active: bool = True
    language: str = "en"   # language of notifications: en | ne
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None