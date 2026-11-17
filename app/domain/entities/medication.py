from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID

from app.domain.value_objects.medication_enums import AlertStyle, IntakeTiming, MedicineType


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
    alert_style: AlertStyle = AlertStyle.NOTIFICATION


@dataclass
class MedicationInventory:
    """Stock of a medicine, counted in whatever unit the user thinks in
    (tablets, ml, puffs ...)."""
    quantity: float                       # units left
    units_per_dose: float = 1.0           # units used each time a dose is taken
    refill_reminder_enabled: bool = True
    remind_days_before: int = 3           # remind this many days before it runs out
    # Which refill alert was already sent for the current stock:
    # None, "early" (N days before) or "final" (the day it runs out).
    alert_stage: Optional[str] = None


@dataclass
class PausedPeriod:
    """A time span during which the medicine was stopped (`until` None = still stopped)."""
    since: datetime
    until: Optional[datetime] = None


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
    inventory: Optional[MedicationInventory] = None
    paused_periods: List[PausedPeriod] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def stopped_at(self) -> Optional[datetime]:
        """When the medicine was stopped, or None while it is active."""
        if self.paused_periods and self.paused_periods[-1].until is None:
            return self.paused_periods[-1].since
        return None

    @property
    def is_stopped(self) -> bool:
        return self.stopped_at is not None

    def was_paused_at(self, when: datetime) -> bool:
        """True if `when` falls inside a stopped period (no dose was expected)."""
        return any(
            p.since <= when and (p.until is None or when < p.until)
            for p in self.paused_periods
        )
