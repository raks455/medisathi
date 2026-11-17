from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator,
)

from app.domain.entities.medication import MedicationSchedule
from app.domain.value_objects.medication_enums import IntakeTiming, MedicineType


def _strip(value):
    return value.strip() if isinstance(value, str) else value


# ---- schedule -----------------------------------------------------------

class ScheduleRequest(BaseModel):
    reminder_times: List[time] = Field(
        ..., min_length=1, max_length=12,
        description="Local times to take the medicine, 24h 'HH:MM'",
        examples=[["08:00", "20:00"]],
    )
    timezone: str = Field("Asia/Kathmandu", description="IANA timezone of the user")
    days_of_week: Optional[List[int]] = Field(
        None, description="0=Mon ... 6=Sun. Omit or null for every day", examples=[None]
    )
    start_date: Optional[date] = None
    end_date: Optional[date] = Field(None, description="Last day of the course (inclusive)")
    reminders_enabled: bool = True

    @field_validator("reminder_times")
    @classmethod
    def _clean_times(cls, v: List[time]) -> List[time]:
        cleaned = sorted({t.replace(second=0, microsecond=0, tzinfo=None) for t in v})
        if len(cleaned) != len(v):
            raise ValueError("reminder_times must not contain duplicates")
        return cleaned

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"Unknown timezone '{v}'")
        return v

    @field_validator("days_of_week")
    @classmethod
    def _valid_days(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is None:
            return None
        if not v:
            raise ValueError("days_of_week must have at least one day, or be null for every day")
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("days_of_week values must be between 0 (Mon) and 6 (Sun)")
        return sorted(set(v))

    @model_validator(mode="after")
    def _valid_range(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self

    def to_entity(self) -> MedicationSchedule:
        return MedicationSchedule(**self.model_dump())


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reminder_times: List[time]
    timezone: str
    days_of_week: Optional[List[int]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reminders_enabled: bool

    @field_serializer("reminder_times")
    def _fmt_times(self, v: List[time]) -> List[str]:
        return [t.strftime("%H:%M") for t in v]


# ---- medication ---------------------------------------------------------

class MedicationCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, examples=["Paracetamol"])
    medicine_type: MedicineType = Field(..., examples=["tablet"])
    dose: str = Field(..., min_length=1, max_length=100, examples=["500 mg"])
    intake_timing: IntakeTiming = Field(..., examples=["after_food"])
    instructions: Optional[str] = Field(
        None, max_length=1000, examples=["Take 1 tablet twice a day with water"]
    )
    schedule: Optional[ScheduleRequest] = Field(
        None, description="Reminder schedule. Omit for 'as needed' medicines."
    )

    _strip_strings = field_validator("name", "dose", "instructions", mode="before")(_strip)


class MedicationUpdateRequest(BaseModel):
    """Partial update: send only the fields you want to change.

    `schedule`: omit to keep it, send an object to replace it, send null to remove it.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=150)
    medicine_type: Optional[MedicineType] = None
    dose: Optional[str] = Field(None, min_length=1, max_length=100)
    intake_timing: Optional[IntakeTiming] = None
    instructions: Optional[str] = Field(None, max_length=1000)
    schedule: Optional[ScheduleRequest] = None

    _strip_strings = field_validator("name", "dose", "instructions", mode="before")(_strip)


class MedicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    medicine_type: MedicineType
    dose: str
    intake_timing: IntakeTiming
    instructions: Optional[str] = None
    schedule: Optional[ScheduleResponse] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
