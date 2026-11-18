from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.domain.value_objects.health_enums import Mood, VitalType


@dataclass
class VitalReading:
    """One measurement. Blood pressure uses value (systolic) and value2
    (diastolic); weight is kg and height is cm."""
    id: UUID
    user_id: UUID
    type: VitalType
    value: float
    recorded_at: datetime
    value2: Optional[float] = None
    pulse: Optional[int] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class MoodEntry:
    """A "how are you feeling right now" check-in."""
    id: UUID
    user_id: UUID
    mood: Mood
    recorded_at: datetime
    note: Optional[str] = None
    tags: List[str] = field(default_factory=list)
