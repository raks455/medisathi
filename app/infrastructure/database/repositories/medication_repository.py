from datetime import time
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.medication import Medication, MedicationSchedule
from app.domain.repositories.medication_respository import MedicationRepository
from app.domain.value_objects.medication_enums import IntakeTiming, MedicineType
from app.infrastructure.database.models.medication import (
    MedicationModel,
    MedicationScheduleModel,
)


class SQLAlchemyMedicationRepository(MedicationRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, medication: Medication) -> Medication:
        model = MedicationModel(
            id=medication.id,
            user_id=medication.user_id,
            name=medication.name,
            medicine_type=medication.medicine_type.value,
            dose=medication.dose,
            intake_timing=medication.intake_timing.value,
            instructions=medication.instructions,
            schedule=self._schedule_to_model(medication.schedule),
        )
        self.session.add(model)
        await self.session.commit()
        return await self.get_by_id(medication.id, medication.user_id)

    async def get_by_id(self, medication_id: UUID, user_id: UUID) -> Optional[Medication]:
        model = await self._get_model(medication_id, user_id)
        return self._to_entity(model) if model else None

    async def list_by_user(self, user_id: UUID) -> List[Medication]:
        result = await self.session.execute(
            select(MedicationModel)
            .where(MedicationModel.user_id == user_id)
            .order_by(MedicationModel.created_at.desc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_with_active_reminders(self) -> List[Medication]:
        result = await self.session.execute(
            select(MedicationModel)
            .join(MedicationScheduleModel)
            .where(MedicationScheduleModel.reminders_enabled.is_(True))
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, medication: Medication) -> Medication:
        model = await self._get_model(medication.id, medication.user_id)
        if not model:
            raise LookupError("Medication not found")
        model.name = medication.name
        model.medicine_type = medication.medicine_type.value
        model.dose = medication.dose
        model.intake_timing = medication.intake_timing.value
        model.instructions = medication.instructions

        new_schedule = medication.schedule
        if new_schedule is None:
            model.schedule = None
        elif model.schedule is None:
            model.schedule = self._schedule_to_model(new_schedule)
        else:
            self._copy_schedule(new_schedule, model.schedule)

        await self.session.commit()
        return await self.get_by_id(medication.id, medication.user_id)

    async def delete(self, medication_id: UUID, user_id: UUID) -> bool:
        result = await self.session.execute(
            delete(MedicationModel).where(
                MedicationModel.id == medication_id,
                MedicationModel.user_id == user_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def _get_model(self, medication_id: UUID, user_id: UUID) -> Optional[MedicationModel]:
        result = await self.session.execute(
            select(MedicationModel)
            .where(
                MedicationModel.id == medication_id,
                MedicationModel.user_id == user_id,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    # ---- mapping helpers -------------------------------------------------

    @staticmethod
    def _copy_schedule(s: MedicationSchedule, model: MedicationScheduleModel) -> None:
        model.reminder_times = [t.strftime("%H:%M") for t in s.reminder_times]
        model.timezone = s.timezone
        model.days_of_week = s.days_of_week
        model.start_date = s.start_date
        model.end_date = s.end_date
        model.reminders_enabled = s.reminders_enabled

    def _schedule_to_model(self, s: Optional[MedicationSchedule]) -> Optional[MedicationScheduleModel]:
        if s is None:
            return None
        model = MedicationScheduleModel()
        self._copy_schedule(s, model)
        return model

    @staticmethod
    def _schedule_to_entity(m: Optional[MedicationScheduleModel]) -> Optional[MedicationSchedule]:
        if m is None:
            return None
        return MedicationSchedule(
            reminder_times=[time.fromisoformat(t) for t in m.reminder_times],
            timezone=m.timezone,
            days_of_week=m.days_of_week,
            start_date=m.start_date,
            end_date=m.end_date,
            reminders_enabled=m.reminders_enabled,
        )

    def _to_entity(self, model: MedicationModel) -> Medication:
        return Medication(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            medicine_type=MedicineType(model.medicine_type),
            dose=model.dose,
            intake_timing=IntakeTiming(model.intake_timing),
            instructions=model.instructions,
            schedule=self._schedule_to_entity(model.schedule),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
