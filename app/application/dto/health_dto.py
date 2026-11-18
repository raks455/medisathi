"""Request / response schemas for health records, vitals, mood, cycle,
pregnancy and feedback."""
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Literal, Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.entities.health_record import HealthRecord
from app.domain.entities.wellness import MoodEntry, VitalReading
from app.domain.entities.womens_health import CyclePeriod
from app.domain.services import vitals as vital_rules
from app.domain.value_objects.health_enums import (
    BloodGroup, FeedbackTopic, Flow, Gender, Mood, RecordCategory, RecordFolder, VitalType,
)


def _clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


# ---- health records -------------------------------------------------------

class HealthRecordResponse(BaseModel):
    id: UUID
    folder: RecordFolder
    category: RecordCategory
    title: str
    notes: Optional[str] = None
    document_date: Optional[date] = None
    file_name: str
    content_type: str
    size_bytes: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    @classmethod
    def from_entity(cls, r: HealthRecord) -> "HealthRecordResponse":
        return cls(**{k: getattr(r, k) for k in cls.model_fields})


class FolderUsage(BaseModel):
    folder: RecordFolder
    count: int
    bytes: int


class HealthRecordSummary(BaseModel):
    folders: List[FolderUsage]
    total_bytes: int
    quota_bytes: int
    max_file_bytes: int


class HealthRecordUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=150)
    category: Optional[RecordCategory] = None
    notes: Optional[str] = Field(None, max_length=2000)
    document_date: Optional[date] = None

    _strip = field_validator("title", "notes", mode="before")(lambda cls, v: _clean(v))


# ---- vitals ---------------------------------------------------------------

class VitalCreateRequest(BaseModel):
    type: VitalType
    value: float = Field(..., description="kg for weight, cm for height, systolic mmHg for BP")
    value2: Optional[float] = Field(None, description="Diastolic mmHg (blood pressure only)")
    pulse: Optional[int] = Field(None, description="Beats per minute (blood pressure only)")
    recorded_at: Optional[datetime] = Field(None, description="Defaults to now")
    note: Optional[str] = Field(None, max_length=300)

    _strip = field_validator("note", mode="before")(lambda cls, v: _clean(v))

    @model_validator(mode="after")
    def _check(self) -> "VitalCreateRequest":
        if self.type == VitalType.WEIGHT:
            if not vital_rules.in_range(self.value, vital_rules.WEIGHT_KG_RANGE):
                raise ValueError("Weight must be between 1 and 500 kg")
        elif self.type == VitalType.HEIGHT:
            if not vital_rules.in_range(self.value, vital_rules.HEIGHT_CM_RANGE):
                raise ValueError("Height must be between 30 and 272 cm")
        else:
            if not vital_rules.in_range(self.value, vital_rules.SYSTOLIC_RANGE):
                raise ValueError("Systolic pressure must be between 50 and 300 mmHg")
            if not vital_rules.in_range(self.value2, vital_rules.DIASTOLIC_RANGE):
                raise ValueError("Diastolic pressure must be between 30 and 200 mmHg")
            if self.value2 >= self.value:
                raise ValueError("Systolic (top) must be higher than diastolic (bottom)")
            if self.pulse is not None and not vital_rules.in_range(
                    self.pulse, vital_rules.PULSE_RANGE):
                raise ValueError("Pulse must be between 20 and 250 bpm")
        if self.type != VitalType.BLOOD_PRESSURE:
            self.value2 = None
            self.pulse = None
        if self.recorded_at is None:
            self.recorded_at = datetime.now(timezone.utc)
        elif self.recorded_at.tzinfo is None:
            self.recorded_at = self.recorded_at.replace(tzinfo=timezone.utc)
        if self.recorded_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("recorded_at cannot be in the future")
        return self


class VitalResponse(BaseModel):
    id: UUID
    type: VitalType
    value: float
    value2: Optional[float] = None
    pulse: Optional[int] = None
    note: Optional[str] = None
    recorded_at: datetime
    category: Optional[str] = Field(
        None, description="Blood pressure category, e.g. normal, elevated, high_stage_1")

    @classmethod
    def from_entity(cls, v: VitalReading) -> "VitalResponse":
        category = None
        if v.type == VitalType.BLOOD_PRESSURE and v.value2 is not None:
            category = vital_rules.blood_pressure_category(int(v.value), int(v.value2))
        return cls(id=v.id, type=v.type, value=v.value, value2=v.value2, pulse=v.pulse,
                   note=v.note, recorded_at=v.recorded_at, category=category)


class VitalsSummary(BaseModel):
    weight: Optional[VitalResponse] = None
    height: Optional[VitalResponse] = None
    blood_pressure: Optional[VitalResponse] = None
    bmi: Optional[float] = None
    bmi_category: Optional[str] = None
    weight_change_30d: Optional[float] = Field(
        None, description="kg gained (+) or lost (-) compared with about 30 days ago")


# ---- mood -----------------------------------------------------------------

class MoodCreateRequest(BaseModel):
    mood: Mood
    note: Optional[str] = Field(None, max_length=500)
    tags: List[str] = Field(default_factory=list, max_length=10,
                            examples=[["tired", "headache"]])

    _strip = field_validator("note", mode="before")(lambda cls, v: _clean(v))

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, v: List[str]) -> List[str]:
        seen: List[str] = []
        for tag in v:
            tag = tag.strip().lower()[:30]
            if tag and tag not in seen:
                seen.append(tag)
        return seen


class MoodResponse(BaseModel):
    id: UUID
    mood: Mood
    note: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    recorded_at: datetime

    @classmethod
    def from_entity(cls, m: MoodEntry) -> "MoodResponse":
        return cls(id=m.id, mood=m.mood, note=m.note, tags=m.tags, recorded_at=m.recorded_at)


class MoodListResponse(BaseModel):
    items: List[MoodResponse]
    counts: Dict[Mood, int] = Field(..., description="How often each mood was logged")


# ---- cycle ----------------------------------------------------------------

class PeriodRequest(BaseModel):
    start_date: date
    end_date: Optional[date] = Field(None, description="Leave empty while it is ongoing")
    flow: Optional[Flow] = None
    notes: Optional[str] = Field(None, max_length=500)

    _strip = field_validator("notes", mode="before")(lambda cls, v: _clean(v))

    @model_validator(mode="after")
    def _check(self) -> "PeriodRequest":
        if self.end_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("end_date must be on or after start_date")
            if (self.end_date - self.start_date).days >= 15:
                raise ValueError("A period cannot be longer than 15 days")
        return self


class PeriodResponse(BaseModel):
    id: UUID
    start_date: date
    end_date: Optional[date] = None
    flow: Optional[Flow] = None
    notes: Optional[str] = None

    @classmethod
    def from_entity(cls, p: CyclePeriod) -> "PeriodResponse":
        return cls(id=p.id, start_date=p.start_date, end_date=p.end_date,
                   flow=p.flow, notes=p.notes)


class CycleWindowResponse(BaseModel):
    period_start: date
    period_end: date
    ovulation_date: date
    fertile_start: date
    fertile_end: date
    predicted: bool


class CycleOverviewResponse(BaseModel):
    average_cycle_length: int
    average_period_length: int
    cycles_logged: int
    last_period_start: Optional[date] = None
    next_period_start: Optional[date] = None
    days_until_next_period: Optional[int] = Field(None, description="Negative when late")
    cycle_day: Optional[int] = None
    phase: Optional[str] = Field(
        None, description="menstrual | follicular | fertile | ovulation | luteal")
    windows: List[CycleWindowResponse] = Field(
        default_factory=list,
        description="The current cycle (predicted=false) followed by predicted ones")
    periods: List[PeriodResponse] = Field(default_factory=list, description="Newest first")


class CycleSettingsRequest(BaseModel):
    timezone: Optional[str] = Field(None, description="IANA timezone of the phone")
    period_reminders: Optional[bool] = Field(None, description="Remind before a period")
    remind_days_before: Optional[int] = Field(None, ge=1, le=7)
    fertile_reminders: Optional[bool] = Field(None, description="Remind when fertile days start")

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"Unknown timezone '{v}'")
        return v


class CycleSettingsResponse(BaseModel):
    timezone: str
    period_reminders: bool
    remind_days_before: int
    fertile_reminders: bool


# ---- pregnancy ------------------------------------------------------------

class PregnancyRequest(BaseModel):
    last_period_date: Optional[date] = Field(None, description="First day of the last period")
    due_date: Optional[date] = Field(None, description="Known due date (from a scan)")
    notes: Optional[str] = Field(None, max_length=500)

    _strip = field_validator("notes", mode="before")(lambda cls, v: _clean(v))

    @model_validator(mode="after")
    def _one_date(self) -> "PregnancyRequest":
        if (self.last_period_date is None) == (self.due_date is None):
            raise ValueError("Give either last_period_date or due_date")
        return self


class PregnancyResponse(BaseModel):
    id: UUID
    last_period_date: date
    due_date: date
    notes: Optional[str] = None
    weeks: int
    days: int
    trimester: int
    days_remaining: int
    percent_complete: float
    baby_size: Optional[str] = Field(None, description="e.g. 'a lemon'")
    tip: str


class PregnancyStatusResponse(BaseModel):
    pregnancy: Optional[PregnancyResponse] = None


# ---- feedback -------------------------------------------------------------

class FeedbackRequest(BaseModel):
    topic: FeedbackTopic = FeedbackTopic.OTHER
    rating: Optional[int] = Field(None, ge=1, le=5)
    message: str = Field(..., min_length=5, max_length=2000)
    app_version: Optional[str] = Field(None, max_length=40)
    platform: Optional[str] = Field(None, max_length=80)

    _strip = field_validator("message", "app_version", "platform", mode="before")(
        lambda cls, v: _clean(v))


# ---- profile --------------------------------------------------------------

def _clean_list(values: List[str]) -> List[str]:
    """Trimmed, without blanks or repeats (ignoring case)."""
    seen: List[str] = []
    for item in values:
        item = " ".join(str(item).split())[:60]
        if item and item.lower() not in (s.lower() for s in seen):
            seen.append(item)
    return seen


class ProfileUpdateRequest(BaseModel):
    """Replaces the whole profile: a field left out is cleared."""
    full_name: str = Field(..., min_length=2, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    blood_group: Optional[BloodGroup] = None
    conditions: List[str] = Field(default_factory=list, max_length=30,
                                  examples=[["Diabetes", "High blood pressure"]])
    allergies: List[str] = Field(default_factory=list, max_length=30)

    @field_validator("full_name", mode="before")
    @classmethod
    def _strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v

    _lists = field_validator("conditions", "allergies")(lambda cls, v: _clean_list(v))

    @field_validator("date_of_birth")
    @classmethod
    def _valid_birth(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            return v
        # A day of slack: the phone may be ahead of UTC.
        today = datetime.now(timezone.utc).date() + timedelta(days=1)
        if v > today:
            raise ValueError("Date of birth cannot be in the future")
        if v.year < today.year - 130:
            raise ValueError("Date of birth is too far in the past")
        return v


class LanguageRequest(BaseModel):
    language: Literal["en", "ne"] = Field(
        ..., description="Language of reminders and other notifications")


class ProfileResponse(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    date_of_birth: Optional[date] = None
    age: Optional[int] = Field(None, description="Full years, from date_of_birth")
    gender: Optional[Gender] = None
    blood_group: Optional[BloodGroup] = None
    conditions: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    language: str = "en"
