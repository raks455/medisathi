from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.domain.value_objects.medication_enums import DoseStatus


@dataclass
class DoseLog:
    id: UUID
    user_id: UUID
    medication_id: UUID
    scheduled_for: datetime          # UTC, tz-aware
    status: DoseStatus
    responded_at: Optional[datetime] = None   # when the user marked taken/skipped
    notified_at: Optional[datetime] = None    # when the server sent a push
