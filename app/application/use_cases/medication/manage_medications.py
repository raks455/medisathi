from dataclasses import replace
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from app.application.dto.medication_dto import (
    MedicationCreateRequest,
    MedicationUpdateRequest,
)
from app.domain.entities.medication import Medication, PausedPeriod
from app.domain.repositories.medication_respository import MedicationRepository

# Fields that may not be cleared to null on update.
_REQUIRED_FIELDS = {"name", "medicine_type", "dose", "intake_timing"}


class CreateMedicationUseCase:
    def __init__(self, repo: MedicationRepository):
        self.repo = repo

    async def execute(self, user_id: UUID, data: MedicationCreateRequest) -> Medication:
        medication = Medication(
            id=uuid4(),
            user_id=user_id,
            name=data.name,
            medicine_type=data.medicine_type,
            dose=data.dose,
            intake_timing=data.intake_timing,
            instructions=data.instructions or None,
            schedule=data.schedule.to_entity() if data.schedule else None,
            inventory=data.inventory.to_entity() if data.inventory else None,
        )
        return await self.repo.create(medication)


class ListMedicationsUseCase:
    def __init__(self, repo: MedicationRepository):
        self.repo = repo

    async def execute(self, user_id: UUID) -> List[Medication]:
        return await self.repo.list_by_user(user_id)


class GetMedicationUseCase:
    def __init__(self, repo: MedicationRepository):
        self.repo = repo

    async def execute(self, user_id: UUID, medication_id: UUID) -> Medication:
        medication = await self.repo.get_by_id(medication_id, user_id)
        if not medication:
            raise LookupError("Medication not found")
        return medication


class UpdateMedicationUseCase:
    def __init__(self, repo: MedicationRepository):
        self.repo = repo

    async def execute(
        self, user_id: UUID, medication_id: UUID, data: MedicationUpdateRequest
    ) -> Medication:
        existing = await self.repo.get_by_id(medication_id, user_id)
        if not existing:
            raise LookupError("Medication not found")

        changes = data.model_dump(exclude_unset=True, exclude={"schedule", "inventory"})
        cleared = sorted(f for f in _REQUIRED_FIELDS if f in changes and changes[f] is None)
        if cleared:
            raise ValueError(f"These fields cannot be null: {', '.join(cleared)}")
        if "instructions" in changes and not changes["instructions"]:
            changes["instructions"] = None

        if "schedule" in data.model_fields_set:
            changes["schedule"] = data.schedule.to_entity() if data.schedule else None

        if "inventory" in data.model_fields_set:
            new = data.inventory.to_entity() if data.inventory else None
            old = existing.inventory
            # A refill or new reminder settings start the refill alerts over
            # (alert_stage stays empty). An edit that leaves them alone must
            # not make an alert that was already sent go out again.
            if new and old and (
                new.quantity <= old.quantity
                and new.units_per_dose == old.units_per_dose
                and new.remind_days_before == old.remind_days_before
            ):
                new.alert_stage = old.alert_stage
            changes["inventory"] = new

        return await self.repo.update(replace(existing, **changes))


class DeleteMedicationUseCase:
    def __init__(self, repo: MedicationRepository):
        self.repo = repo

    async def execute(self, user_id: UUID, medication_id: UUID) -> None:
        if not await self.repo.delete(medication_id, user_id):
            raise LookupError("Medication not found")


class StopMedicationUseCase:
    """Stop a medicine: no more doses or reminders, but its history is kept."""

    def __init__(self, repo: MedicationRepository):
        self.repo = repo

    async def execute(
        self, user_id: UUID, medication_id: UUID, now: Optional[datetime] = None
    ) -> Medication:
        med = await self.repo.get_by_id(medication_id, user_id)
        if not med:
            raise LookupError("Medication not found")
        if med.is_stopped:
            return med
        now = now or datetime.now(timezone.utc)
        periods = [*med.paused_periods, PausedPeriod(since=now)]
        return await self.repo.update(replace(med, paused_periods=periods))


class ResumeMedicationUseCase:
    """Start a stopped medicine again. Doses during the stop are not counted as missed."""

    def __init__(self, repo: MedicationRepository):
        self.repo = repo

    async def execute(
        self, user_id: UUID, medication_id: UUID, now: Optional[datetime] = None
    ) -> Medication:
        med = await self.repo.get_by_id(medication_id, user_id)
        if not med:
            raise LookupError("Medication not found")
        if not med.is_stopped:
            return med
        now = now or datetime.now(timezone.utc)
        periods = [*med.paused_periods[:-1], replace(med.paused_periods[-1], until=now)]
        return await self.repo.update(replace(med, paused_periods=periods))
