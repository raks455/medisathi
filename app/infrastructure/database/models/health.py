"""Tables for health records, vitals, mood, cycle, pregnancy and feedback.

Enum-like columns are plain strings validated by the API, like the
medication tables, so new options need no migration.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String,
    Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


def _user_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HealthRecordModel(Base):
    __tablename__ = "health_records"
    __table_args__ = (Index("ix_health_records_user_folder", "user_id", "folder"),)

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = _user_fk()
    folder: Mapped[str] = mapped_column(String(30), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class HealthRecordFileModel(Base):
    """File bytes, kept apart so listing records never loads them.

    Stored in Postgres because the app server's disk is not persistent.
    """
    __tablename__ = "health_record_files"

    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("health_records.id", ondelete="CASCADE"),
        primary_key=True,
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class VitalReadingModel(Base):
    __tablename__ = "vital_readings"
    __table_args__ = (Index("ix_vitals_user_type_time", "user_id", "type", "recorded_at"),)

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = _user_fk()
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    value2: Mapped[float | None] = mapped_column(Float, nullable=True)
    pulse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()


class MoodEntryModel(Base):
    __tablename__ = "mood_entries"
    __table_args__ = (Index("ix_moods_user_time", "user_id", "recorded_at"),)

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = _user_fk()
    mood: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CyclePeriodModel(Base):
    __tablename__ = "cycle_periods"
    __table_args__ = (Index("ix_cycle_periods_user_start", "user_id", "start_date"),)

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = _user_fk()
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    flow: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = _created()


class PregnancyModel(Base):
    __tablename__ = "pregnancies"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True,  # one tracked pregnancy per user
    )
    last_period_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = _created()


class FeedbackModel(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = _user_fk()
    topic: Mapped[str] = mapped_column(String(20), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = _created()


class CycleSettingsModel(Base):
    __tablename__ = "cycle_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kathmandu")
    period_reminders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remind_days_before: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    fertile_reminders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alert_key: Mapped[str | None] = mapped_column(String(60), nullable=True)


class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(5), nullable=True)
    conditions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    allergies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
