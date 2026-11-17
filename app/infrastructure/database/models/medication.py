import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func,
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

    medication: Mapped[MedicationModel] = relationship(back_populates="schedule")


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
