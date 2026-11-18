from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional
from uuid import UUID

from app.domain.value_objects.health_enums import BloodGroup, Gender


@dataclass
class UserProfile:
    """Personal health details the user fills in on their profile."""
    user_id: UUID
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    blood_group: Optional[BloodGroup] = None
    conditions: List[str] = field(default_factory=list)  # ongoing diseases
    allergies: List[str] = field(default_factory=list)

    def age(self, today: date) -> Optional[int]:
        born = self.date_of_birth
        if born is None:
            return None
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
