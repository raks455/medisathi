import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base


class MedicationModel(Base):
    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    # Stored as plain strings (validated by the API) so new options can be
    # added to the enums without a database migration.
    medicine_type: Mapped[str] = mapped_column(String(30), nullable=False)
    dose: Mapped[str] = mapped_column(String(100), nullable=False)
    intake_timing: Mapped[str] = mapped_column(String(30), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{"since": iso, "until": iso | null}] - spans in which the medicine was
    # stopped. Added by run_startup_migrations() on existing databases.
    paused_periods: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Set when a photo is stored in medication_photos; null = no photo.
    # Added by run_startup_migrations() on existing databases.
    photo_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    schedule: Mapped["MedicationScheduleModel | None"] = relationship(
        back_populates="medication",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    inventory: Mapped["MedicationInventoryModel | None"] = relationship(
        back_populates="medication",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class MedicationScheduleModel(Base):
    """Kept in its own table so the existing `medications` table needs no ALTER."""
    __tablename__ = "medication_schedules"

    medication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    reminder_times: Mapped[list] = mapped_column(JSON, nullable=False)   # ["08:00", "20:00"]
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    days_of_week: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [0..6] or null
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Added by run_startup_migrations() on existing databases.
    alert_style: Mapped[str] = mapped_column(
        String(20), default="notification", server_default="notification", nullable=False
    )

    medication: Mapped[MedicationModel] = relationship(back_populates="schedule")


class MedicationInventoryModel(Base):
    """Stock of a medicine; its own table so `medications` needs no ALTER."""
    __tablename__ = "medication_inventories"

    medication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    units_per_dose: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    refill_reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remind_days_before: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    # Refill alert already sent for the current stock: null, "early" or "final".
    alert_stage: Mapped[str | None] = mapped_column(String(10), nullable=True)

    medication: Mapped[MedicationModel] = relationship(back_populates="inventory")


class DoseLogModel(Base):
    __tablename__ = "dose_logs"
    __table_args__ = (
        UniqueConstraint("medication_id", "scheduled_for", name="uq_dose_logs_med_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    medication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medications.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MedicationPhotoModel(Base):
    """The user's photo of a medicine (the strip, bottle or pill).

    Kept apart from `medications` so listing medicines never loads the bytes,
    and in Postgres because the app server's disk is not persistent.
    """
    __tablename__ = "medication_photos"

    medication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
