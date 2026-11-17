from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID

from app.domain.value_objects.medication_enums import IntakeTiming, MedicineType


@dataclass
class MedicationSchedule:
    """When a medicine should be taken. Times are in the user's local timezone."""
    reminder_times: List[time]
    timezone: str = "Asia/Kathmandu"
    # 0 = Monday ... 6 = Sunday. None means every day.
    days_of_week: Optional[List[int]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reminders_enabled: bool = True


@dataclass
class Medication:
    id: UUID
    user_id: UUID
    name: str
    medicine_type: MedicineType
    dose: str
    intake_timing: IntakeTiming
    instructions: Optional[str] = None
    schedule: Optional[MedicationSchedule] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
