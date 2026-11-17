from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from app.domain.value_objects.medication_enums import NotificationType


@dataclass
class Notification:
    """One entry in the user's in-app notification list."""
    id: UUID
    user_id: UUID
    type: NotificationType
    title: str
    body: str
    data: Dict[str, str] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
