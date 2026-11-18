from datetime import date, datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain.value_objects.medication_enums import (
    DoseViewStatus, IntakeTiming, MedicineType,
)


class ScheduledDose(BaseModel):
    dose_key: str = Field(..., description="Use as the local-notification id/tag on the app")
    medication_id: UUID
    medication_name: str
    medicine_type: MedicineType
    dose: str
    intake_timing: IntakeTiming
    instructions: Optional[str] = None
    scheduled_for: datetime = Field(..., description="UTC time of the dose")
    local_date: date
    local_time: str = Field(..., description="'HH:MM' in the schedule's timezone")
    timezone: str
    status: DoseViewStatus
    responded_at: Optional[datetime] = None
    photo_url: Optional[str] = Field(None, description="The user's photo of the medicine")


class AdherenceSummary(BaseModel):
    total: int
    taken: int
    skipped: int
    missed: int
    due: int
    upcoming: int
    adherence_percent: Optional[float] = Field(
        None, description="taken / (taken + skipped + missed); null if nothing is past yet"
    )


class DoseScheduleResponse(BaseModel):
    start_date: date
    end_date: date
    summary: AdherenceSummary
    doses: List[ScheduledDose]


class LogDoseRequest(BaseModel):
    medication_id: UUID
    scheduled_for: datetime = Field(
        ..., description="The dose's `scheduled_for` from the schedule, with timezone"
    )
    status: Literal["taken", "skipped"]

    @field_validator("scheduled_for")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("scheduled_for must include a timezone, e.g. 2026-11-12T02:15:00Z")
        return v


class DoseLogResponse(BaseModel):
    id: UUID
    dose_key: str
    medication_id: UUID
    scheduled_for: datetime
    status: str
    responded_at: Optional[datetime] = None


class RegisterDeviceRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=512, description="FCM registration token")
    platform: Optional[Literal["android", "ios", "web"]] = None
