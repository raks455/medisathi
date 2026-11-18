import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.feedback import Feedback
from app.domain.entities.health_record import HealthRecord
from app.domain.entities.user_profile import UserProfile
from app.domain.entities.wellness import MoodEntry, VitalReading
from app.domain.entities.womens_health import CyclePeriod, CycleSettings, Pregnancy
from app.domain.repositories.health_repositories import (
    CycleRepository, FeedbackRepository, HealthRecordRepository, MoodRepository,
    PregnancyRepository, UserProfileRepository, VitalRepository,
)
from app.domain.value_objects.health_enums import (
    BloodGroup, FeedbackTopic, Flow, Gender, Mood, RecordCategory, RecordFolder, VitalType,
)
from app.infrastructure.database.models.health import (
    CyclePeriodModel, CycleSettingsModel, FeedbackModel, HealthRecordFileModel, HealthRecordModel,
    MoodEntryModel, PregnancyModel, UserProfileModel, VitalReadingModel,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _delete(session: AsyncSession, model, user_id: UUID, row_id: UUID) -> bool:
    result = await session.execute(
        delete(model).where(model.id == row_id, model.user_id == user_id)
    )
    await session.commit()
    return result.rowcount > 0


# ---- health records -------------------------------------------------------

class SQLAlchemyHealthRecordRepository(HealthRecordRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, record: HealthRecord, data: bytes) -> HealthRecord:
        model = HealthRecordModel(
            id=record.id,
            user_id=record.user_id,
            folder=record.folder.value,
            category=record.category.value,
            title=record.title,
            notes=record.notes,
            document_date=record.document_date,
            file_name=record.file_name,
            content_type=record.content_type,
            size_bytes=record.size_bytes,
            created_at=_now(),
        )
        self.session.add(model)
        await self.session.flush()  # the file row references the record
        self.session.add(HealthRecordFileModel(record_id=record.id, data=data))
        await self.session.commit()
        return self._to_entity(model)

    async def list(self, user_id: UUID, folder: Optional[RecordFolder] = None,
                   category: Optional[RecordCategory] = None) -> List[HealthRecord]:
        query = select(HealthRecordModel).where(HealthRecordModel.user_id == user_id)
        if folder:
            query = query.where(HealthRecordModel.folder == folder.value)
        if category:
            query = query.where(HealthRecordModel.category == category.value)
        query = query.order_by(
            HealthRecordModel.document_date.desc().nulls_last(),
            HealthRecordModel.created_at.desc(),
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def _get_model(self, user_id: UUID, record_id: UUID) -> Optional[HealthRecordModel]:
        result = await self.session.execute(
            select(HealthRecordModel).where(
                HealthRecordModel.id == record_id, HealthRecordModel.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get(self, user_id: UUID, record_id: UUID) -> Optional[HealthRecord]:
        model = await self._get_model(user_id, record_id)
        return self._to_entity(model) if model else None

    async def get_file(self, user_id: UUID, record_id: UUID) -> Optional[bytes]:
        result = await self.session.execute(
            select(HealthRecordFileModel.data)
            .join(HealthRecordModel, HealthRecordModel.id == HealthRecordFileModel.record_id)
            .where(HealthRecordModel.id == record_id, HealthRecordModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update(self, record: HealthRecord) -> HealthRecord:
        model = await self._get_model(record.user_id, record.id)
        if model is None:
            raise LookupError("Record not found")
        model.folder = record.folder.value
        model.category = record.category.value
        model.title = record.title
        model.notes = record.notes
        model.document_date = record.document_date
        model.updated_at = _now()
        await self.session.commit()
        return self._to_entity(model)

    async def delete(self, user_id: UUID, record_id: UUID) -> bool:
        return await _delete(self.session, HealthRecordModel, user_id, record_id)

    async def usage(self, user_id: UUID) -> Dict[str, Dict[str, int]]:
        result = await self.session.execute(
            select(
                HealthRecordModel.folder,
                func.count(),
                func.coalesce(func.sum(HealthRecordModel.size_bytes), 0),
            )
            .where(HealthRecordModel.user_id == user_id)
            .group_by(HealthRecordModel.folder)
        )
        return {folder: {"count": count, "bytes": int(size)}
                for folder, count, size in result.all()}

    @staticmethod
    def _to_entity(m: HealthRecordModel) -> HealthRecord:
        return HealthRecord(
            id=m.id,
            user_id=m.user_id,
            folder=RecordFolder(m.folder),
            category=RecordCategory(m.category),
            title=m.title,
            notes=m.notes,
            document_date=m.document_date,
            file_name=m.file_name,
            content_type=m.content_type,
            size_bytes=m.size_bytes,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


# ---- vitals ---------------------------------------------------------------

class SQLAlchemyVitalRepository(VitalRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, reading: VitalReading) -> VitalReading:
        model = VitalReadingModel(
            id=reading.id,
            user_id=reading.user_id,
            type=reading.type.value,
            value=reading.value,
            value2=reading.value2,
            pulse=reading.pulse,
            note=reading.note,
            recorded_at=reading.recorded_at,
            created_at=_now(),
        )
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def list(self, user_id: UUID, type: Optional[VitalType] = None,
                   since: Optional[datetime] = None, limit: int = 100) -> List[VitalReading]:
        query = select(VitalReadingModel).where(VitalReadingModel.user_id == user_id)
        if type:
            query = query.where(VitalReadingModel.type == type.value)
        if since:
            query = query.where(VitalReadingModel.recorded_at >= since)
        query = query.order_by(VitalReadingModel.recorded_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def latest(self, user_id: UUID, type: VitalType) -> Optional[VitalReading]:
        rows = await self.list(user_id, type, limit=1)
        return rows[0] if rows else None

    async def _get_model(self, user_id: UUID, reading_id: UUID) -> Optional[VitalReadingModel]:
        result = await self.session.execute(
            select(VitalReadingModel).where(
                VitalReadingModel.id == reading_id, VitalReadingModel.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get(self, user_id: UUID, reading_id: UUID) -> Optional[VitalReading]:
        model = await self._get_model(user_id, reading_id)
        return self._to_entity(model) if model else None

    async def update(self, reading: VitalReading) -> VitalReading:
        model = await self._get_model(reading.user_id, reading.id)
        if model is None:
            raise LookupError("Reading not found")
        model.value = reading.value
        model.value2 = reading.value2
        model.pulse = reading.pulse
        model.note = reading.note
        model.recorded_at = reading.recorded_at
        await self.session.commit()
        return self._to_entity(model)

    async def delete(self, user_id: UUID, reading_id: UUID) -> bool:
        return await _delete(self.session, VitalReadingModel, user_id, reading_id)

    @staticmethod
    def _to_entity(m: VitalReadingModel) -> VitalReading:
        return VitalReading(
            id=m.id,
            user_id=m.user_id,
            type=VitalType(m.type),
            value=m.value,
            value2=m.value2,
            pulse=m.pulse,
            note=m.note,
            recorded_at=m.recorded_at,
            created_at=m.created_at,
        )


# ---- mood -----------------------------------------------------------------

class SQLAlchemyMoodRepository(MoodRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, entry: MoodEntry) -> MoodEntry:
        model = MoodEntryModel(
            id=entry.id,
            user_id=entry.user_id,
            mood=entry.mood.value,
            note=entry.note,
            tags=list(entry.tags),
            recorded_at=entry.recorded_at,
        )
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def list(self, user_id: UUID, since: Optional[datetime] = None,
                   limit: int = 100) -> List[MoodEntry]:
        query = select(MoodEntryModel).where(MoodEntryModel.user_id == user_id)
        if since:
            query = query.where(MoodEntryModel.recorded_at >= since)
        query = query.order_by(MoodEntryModel.recorded_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def delete(self, user_id: UUID, entry_id: UUID) -> bool:
        return await _delete(self.session, MoodEntryModel, user_id, entry_id)

    @staticmethod
    def _to_entity(m: MoodEntryModel) -> MoodEntry:
        return MoodEntry(
            id=m.id,
            user_id=m.user_id,
            mood=Mood(m.mood),
            note=m.note,
            tags=list(m.tags or []),
            recorded_at=m.recorded_at,
        )


# ---- cycle ----------------------------------------------------------------

class SQLAlchemyCycleRepository(CycleRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, period: CyclePeriod) -> CyclePeriod:
        model = CyclePeriodModel(
            id=period.id,
            user_id=period.user_id,
            start_date=period.start_date,
            end_date=period.end_date,
            flow=period.flow.value if period.flow else None,
            notes=period.notes,
            created_at=_now(),
        )
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def list(self, user_id: UUID) -> List[CyclePeriod]:
        result = await self.session.execute(
            select(CyclePeriodModel)
            .where(CyclePeriodModel.user_id == user_id)
            .order_by(CyclePeriodModel.start_date.desc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def _get_model(self, user_id: UUID, period_id: UUID) -> Optional[CyclePeriodModel]:
        result = await self.session.execute(
            select(CyclePeriodModel).where(
                CyclePeriodModel.id == period_id, CyclePeriodModel.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get(self, user_id: UUID, period_id: UUID) -> Optional[CyclePeriod]:
        model = await self._get_model(user_id, period_id)
        return self._to_entity(model) if model else None

    async def update(self, period: CyclePeriod) -> CyclePeriod:
        model = await self._get_model(period.user_id, period.id)
        if model is None:
            raise LookupError("Period not found")
        model.start_date = period.start_date
        model.end_date = period.end_date
        model.flow = period.flow.value if period.flow else None
        model.notes = period.notes
        await self.session.commit()
        return self._to_entity(model)

    async def delete(self, user_id: UUID, period_id: UUID) -> bool:
        return await _delete(self.session, CyclePeriodModel, user_id, period_id)

    async def get_settings(self, user_id: UUID) -> CycleSettings:
        model = await self.session.get(CycleSettingsModel, user_id)
        return self._settings(model) if model else CycleSettings(user_id=user_id)

    async def save_settings(self, settings: CycleSettings) -> CycleSettings:
        model = await self.session.get(CycleSettingsModel, settings.user_id)
        if model is None:
            model = CycleSettingsModel(user_id=settings.user_id)
            self.session.add(model)
        model.timezone = settings.timezone
        model.period_reminders = settings.period_reminders
        model.remind_days_before = settings.remind_days_before
        model.fertile_reminders = settings.fertile_reminders
        await self.session.commit()
        return self._settings(model)

    async def list_reminder_settings(self) -> List[CycleSettings]:
        result = await self.session.execute(
            select(CycleSettingsModel).where(or_(
                CycleSettingsModel.period_reminders.is_(True),
                CycleSettingsModel.fertile_reminders.is_(True),
            ))
        )
        return [self._settings(m) for m in result.scalars().all()]

    async def claim_alert(self, user_id: UUID, key: str) -> bool:
        result = await self.session.execute(
            update(CycleSettingsModel)
            .where(
                CycleSettingsModel.user_id == user_id,
                or_(CycleSettingsModel.alert_key.is_(None),
                    CycleSettingsModel.alert_key != key),
            )
            .values(alert_key=key)
        )
        await self.session.commit()
        return result.rowcount > 0

    @staticmethod
    def _settings(m: CycleSettingsModel) -> CycleSettings:
        return CycleSettings(
            user_id=m.user_id,
            timezone=m.timezone,
            period_reminders=m.period_reminders,
            remind_days_before=m.remind_days_before,
            fertile_reminders=m.fertile_reminders,
            alert_key=m.alert_key,
        )

    @staticmethod
    def _to_entity(m: CyclePeriodModel) -> CyclePeriod:
        return CyclePeriod(
            id=m.id,
            user_id=m.user_id,
            start_date=m.start_date,
            end_date=m.end_date,
            flow=Flow(m.flow) if m.flow else None,
            notes=m.notes,
            created_at=m.created_at,
        )


# ---- pregnancy ------------------------------------------------------------

class SQLAlchemyPregnancyRepository(PregnancyRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_model(self, user_id: UUID) -> Optional[PregnancyModel]:
        result = await self.session.execute(
            select(PregnancyModel).where(PregnancyModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_active(self, user_id: UUID) -> Optional[Pregnancy]:
        model = await self._get_model(user_id)
        return self._to_entity(model) if model else None

    async def save(self, pregnancy: Pregnancy) -> Pregnancy:
        model = await self._get_model(pregnancy.user_id)
        if model is None:
            model = PregnancyModel(
                id=pregnancy.id, user_id=pregnancy.user_id, created_at=_now()
            )
            self.session.add(model)
        model.last_period_date = pregnancy.last_period_date
        model.due_date = pregnancy.due_date
        model.notes = pregnancy.notes
        await self.session.commit()
        return self._to_entity(model)

    async def delete(self, user_id: UUID, pregnancy_id: UUID) -> bool:
        return await _delete(self.session, PregnancyModel, user_id, pregnancy_id)

    @staticmethod
    def _to_entity(m: PregnancyModel) -> Pregnancy:
        return Pregnancy(
            id=m.id,
            user_id=m.user_id,
            last_period_date=m.last_period_date,
            due_date=m.due_date,
            notes=m.notes,
            created_at=m.created_at,
        )


# ---- feedback -------------------------------------------------------------

class SQLAlchemyFeedbackRepository(FeedbackRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, feedback: Feedback) -> Feedback:
        model = FeedbackModel(
            id=feedback.id or uuid.uuid4(),
            user_id=feedback.user_id,
            topic=feedback.topic.value,
            rating=feedback.rating,
            message=feedback.message,
            app_version=feedback.app_version,
            platform=feedback.platform,
            created_at=_now(),
        )
        self.session.add(model)
        await self.session.commit()
        return Feedback(
            id=model.id,
            user_id=model.user_id,
            topic=FeedbackTopic(model.topic),
            rating=model.rating,
            message=model.message,
            app_version=model.app_version,
            platform=model.platform,
            created_at=model.created_at,
        )


# ---- profile --------------------------------------------------------------

class SQLAlchemyUserProfileRepository(UserProfileRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: UUID) -> UserProfile:
        model = await self.session.get(UserProfileModel, user_id)
        return self._to_entity(model) if model else UserProfile(user_id=user_id)

    async def save(self, profile: UserProfile) -> UserProfile:
        model = await self.session.get(UserProfileModel, profile.user_id)
        if model is None:
            model = UserProfileModel(user_id=profile.user_id)
            self.session.add(model)
        model.date_of_birth = profile.date_of_birth
        model.gender = profile.gender.value if profile.gender else None
        model.blood_group = profile.blood_group.value if profile.blood_group else None
        model.conditions = list(profile.conditions)
        model.allergies = list(profile.allergies)
        await self.session.commit()
        return self._to_entity(model)

    @staticmethod
    def _to_entity(m: UserProfileModel) -> UserProfile:
        return UserProfile(
            user_id=m.user_id,
            date_of_birth=m.date_of_birth,
            gender=Gender(m.gender) if m.gender else None,
            blood_group=BloodGroup(m.blood_group) if m.blood_group else None,
            conditions=list(m.conditions or []),
            allergies=list(m.allergies or []),
        )
