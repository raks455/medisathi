from datetime import date, datetime, time, timezone
from typing import List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator,
)

from app.domain.entities.medication import Medication, MedicationInventory, MedicationSchedule
from app.domain.services.inventory_forecast import forecast_stock, is_low_stock
from app.domain.value_objects.medication_enums import AlertStyle, IntakeTiming, MedicineType
from app.infrastructure.security.photo_links import medicine_photo_url


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
    alert_style: AlertStyle = Field(
        AlertStyle.NOTIFICATION,
        description="'notification' = normal sound, 'alarm' = alarm sound and strong vibration",
    )

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
    alert_style: AlertStyle = AlertStyle.NOTIFICATION

    @field_serializer("reminder_times")
    def _fmt_times(self, v: List[time]) -> List[str]:
        return [t.strftime("%H:%M") for t in v]


# ---- inventory ----------------------------------------------------------

class InventoryRequest(BaseModel):
    quantity: float = Field(
        ..., ge=0, le=100000,
        description="Units in stock now (tablets, ml, puffs ...)", examples=[30],
    )
    units_per_dose: float = Field(
        1, gt=0, le=1000, description="Units used each time a dose is taken", examples=[1],
    )
    refill_reminder_enabled: bool = True
    remind_days_before: int = Field(
        3, ge=0, le=30,
        description="Send the refill reminder this many days before the stock runs out "
                    "(a second one is always sent on the day it runs out)",
    )

    def to_entity(self) -> MedicationInventory:
        return MedicationInventory(**self.model_dump())


class InventoryResponse(BaseModel):
    quantity: float
    units_per_dose: float
    refill_reminder_enabled: bool
    remind_days_before: int
    doses_left: int = Field(..., description="Full doses the stock still covers")
    runs_out_on: Optional[date] = Field(
        None, description="Estimated day the stock runs out; null if it cannot be "
                          "estimated (no schedule, stopped, or enough for the course)",
    )
    days_left: Optional[int] = Field(None, description="Days until `runs_out_on` (0 = today)")
    low_stock: bool = Field(..., description="True once inside the refill-reminder window")


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
    inventory: Optional[InventoryRequest] = Field(
        None, description="Stock tracking and refill reminders. Omit to not track stock."
    )

    _strip_strings = field_validator("name", "dose", "instructions", mode="before")(_strip)


class MedicationUpdateRequest(BaseModel):
    """Partial update: send only the fields you want to change.

    `schedule` / `inventory`: omit to keep it, send an object to replace it,
    send null to remove it.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=150)
    medicine_type: Optional[MedicineType] = None
    dose: Optional[str] = Field(None, min_length=1, max_length=100)
    intake_timing: Optional[IntakeTiming] = None
    instructions: Optional[str] = Field(None, max_length=1000)
    schedule: Optional[ScheduleRequest] = None
    inventory: Optional[InventoryRequest] = None

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
    inventory: Optional[InventoryResponse] = None
    is_stopped: bool = False
    stopped_at: Optional[datetime] = None
    photo_url: Optional[str] = Field(
        None, description="The user's photo of the medicine. Opens without a token; "
                          "changes whenever the photo does")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_entity(cls, med: Medication, now: Optional[datetime] = None) -> "MedicationResponse":
        """Build the response, adding the stock forecast (which depends on `now`)."""
        inventory = None
        if med.inventory is not None:
            forecast = forecast_stock(med, now or datetime.now(timezone.utc))
            inventory = InventoryResponse(
                quantity=med.inventory.quantity,
                units_per_dose=med.inventory.units_per_dose,
                refill_reminder_enabled=med.inventory.refill_reminder_enabled,
                remind_days_before=med.inventory.remind_days_before,
                doses_left=forecast.doses_left,
                runs_out_on=forecast.runs_out_on,
                days_left=forecast.days_left,
                low_stock=is_low_stock(med, forecast),
            )
        return cls(
            id=med.id,
            name=med.name,
            medicine_type=med.medicine_type,
            dose=med.dose,
            intake_timing=med.intake_timing,
            instructions=med.instructions,
            schedule=ScheduleResponse.model_validate(med.schedule) if med.schedule else None,
            inventory=inventory,
            is_stopped=med.is_stopped,
            stopped_at=med.stopped_at,
            photo_url=medicine_photo_url(med),
            created_at=med.created_at,
            updated_at=med.updated_at,
        )
