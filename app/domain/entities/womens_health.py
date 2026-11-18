from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from app.domain.value_objects.health_enums import Flow


@dataclass
class CyclePeriod:
    """One logged period. end_date is None while it is ongoing."""
    id: UUID
    user_id: UUID
    start_date: date
    end_date: Optional[date] = None
    flow: Optional[Flow] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Pregnancy:
    id: UUID
    user_id: UUID
    last_period_date: date
    due_date: date
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class CycleSettings:
    """Period reminder preferences. alert_key remembers the last reminder
    sent so each one goes out once."""
    user_id: UUID
    timezone: str = "Asia/Kathmandu"
    period_reminders: bool = True
    remind_days_before: int = 2
    fertile_reminders: bool = False
    alert_key: Optional[str] = None
