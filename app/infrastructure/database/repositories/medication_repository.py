from datetime import datetime, time, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.medication import (
    Medication, MedicationInventory, MedicationSchedule, PausedPeriod,
)
from app.domain.repositories.medication_respository import MedicationRepository
from app.domain.value_objects.medication_enums import AlertStyle, IntakeTiming, MedicineType
from app.infrastructure.database.models.medication import (
    MedicationInventoryModel,
    MedicationModel,
    MedicationPhotoModel,
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
            paused_periods=self._pauses_to_json(medication.paused_periods),
            schedule=self._schedule_to_model(medication.schedule),
            inventory=self._inventory_to_model(medication.inventory),
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
            # Stock changes through adjust_inventory(), outside the ORM.
            .execution_options(populate_existing=True)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_with_active_reminders(self) -> List[Medication]:
        result = await self.session.execute(
            select(MedicationModel)
            .join(MedicationScheduleModel)
            .where(MedicationScheduleModel.reminders_enabled.is_(True))
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_with_refill_reminders(self) -> List[Medication]:
        result = await self.session.execute(
            select(MedicationModel)
            .join(MedicationScheduleModel)
            .join(MedicationInventoryModel)
            .where(MedicationInventoryModel.refill_reminder_enabled.is_(True))
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
        model.paused_periods = self._pauses_to_json(medication.paused_periods)

        new_schedule = medication.schedule
        if new_schedule is None:
            model.schedule = None
        elif model.schedule is None:
            model.schedule = self._schedule_to_model(new_schedule)
        else:
            self._copy_schedule(new_schedule, model.schedule)

        new_inventory = medication.inventory
        if new_inventory is None:
            model.inventory = None
        elif model.inventory is None:
            model.inventory = self._inventory_to_model(new_inventory)
        else:
            self._copy_inventory(new_inventory, model.inventory)

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

    async def adjust_inventory(self, medication_id: UUID, delta: float) -> None:
        # One UPDATE so two doses marked at the same moment both count.
        await self.session.execute(
            update(MedicationInventoryModel)
            .where(MedicationInventoryModel.medication_id == medication_id)
            .values(quantity=func.greatest(0, MedicationInventoryModel.quantity + delta))
        )
        await self.session.commit()

    async def claim_refill_alert(self, medication_id: UUID, stage: str) -> bool:
        result = await self.session.execute(
            update(MedicationInventoryModel)
            .where(
                MedicationInventoryModel.medication_id == medication_id,
                MedicationInventoryModel.alert_stage.is_distinct_from(stage),
            )
            .values(alert_stage=stage)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def set_photo(self, medication_id: UUID, data: bytes, content_type: str) -> None:
        photo = await self.session.get(MedicationPhotoModel, medication_id)
        if photo is None:
            photo = MedicationPhotoModel(medication_id=medication_id)
            self.session.add(photo)
        photo.data = data
        photo.content_type = content_type
        # Milliseconds since 1970: a new value for every upload.
        version = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        await self.session.execute(
            update(MedicationModel)
            .where(MedicationModel.id == medication_id)
            .values(photo_version=version)
        )
        await self.session.commit()

    async def delete_photo(self, medication_id: UUID) -> None:
        await self.session.execute(
            delete(MedicationPhotoModel)
            .where(MedicationPhotoModel.medication_id == medication_id)
        )
        await self.session.execute(
            update(MedicationModel)
            .where(MedicationModel.id == medication_id)
            .values(photo_version=None)
        )
        await self.session.commit()

    async def get_photo(self, medication_id: UUID, version: str) -> Optional[Tuple[bytes, str]]:
        result = await self.session.execute(
            select(MedicationPhotoModel.data, MedicationPhotoModel.content_type)
            .join(MedicationModel, MedicationModel.id == MedicationPhotoModel.medication_id)
            .where(MedicationModel.id == medication_id,
                   MedicationModel.photo_version == version)
        )
        row = result.first()
        return (row[0], row[1]) if row else None

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
        model.alert_style = AlertStyle(s.alert_style).value

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
            alert_style=AlertStyle(m.alert_style or AlertStyle.NOTIFICATION.value),
        )

    @staticmethod
    def _copy_inventory(inv: MedicationInventory, model: MedicationInventoryModel) -> None:
        model.quantity = inv.quantity
        model.units_per_dose = inv.units_per_dose
        model.refill_reminder_enabled = inv.refill_reminder_enabled
        model.remind_days_before = inv.remind_days_before
        model.alert_stage = inv.alert_stage

    def _inventory_to_model(
        self, inv: Optional[MedicationInventory]
    ) -> Optional[MedicationInventoryModel]:
        if inv is None:
            return None
        model = MedicationInventoryModel()
        self._copy_inventory(inv, model)
        return model

    @staticmethod
    def _inventory_to_entity(
        m: Optional[MedicationInventoryModel],
    ) -> Optional[MedicationInventory]:
        if m is None:
            return None
        return MedicationInventory(
            quantity=m.quantity,
            units_per_dose=m.units_per_dose,
            refill_reminder_enabled=m.refill_reminder_enabled,
            remind_days_before=m.remind_days_before,
            alert_stage=m.alert_stage,
        )

    @staticmethod
    def _pauses_to_json(periods: List[PausedPeriod]) -> Optional[list]:
        if not periods:
            return None
        return [
            {"since": p.since.isoformat(), "until": p.until.isoformat() if p.until else None}
            for p in periods
        ]

    @staticmethod
    def _pauses_to_entity(raw: Optional[list]) -> List[PausedPeriod]:
        return [
            PausedPeriod(
                since=datetime.fromisoformat(p["since"]),
                until=datetime.fromisoformat(p["until"]) if p.get("until") else None,
            )
            for p in (raw or [])
        ]

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
            inventory=self._inventory_to_entity(model.inventory),
            paused_periods=self._pauses_to_entity(model.paused_periods),
            photo_version=model.photo_version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
