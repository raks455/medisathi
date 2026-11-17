from dataclasses import replace
from typing import List
from uuid import UUID, uuid4

from app.application.dto.medication_dto import (
    MedicationCreateRequest,
    MedicationUpdateRequest,
)
from app.domain.entities.medication import Medication
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

        changes = data.model_dump(exclude_unset=True, exclude={"schedule"})
        cleared = sorted(f for f in _REQUIRED_FIELDS if f in changes and changes[f] is None)
        if cleared:
            raise ValueError(f"These fields cannot be null: {', '.join(cleared)}")
        if "instructions" in changes and not changes["instructions"]:
            changes["instructions"] = None

        if "schedule" in data.model_fields_set:
            changes["schedule"] = data.schedule.to_entity() if data.schedule else None

        return await self.repo.update(replace(existing, **changes))


class DeleteMedicationUseCase:
    def __init__(self, repo: MedicationRepository):
        self.repo = repo

    async def execute(self, user_id: UUID, medication_id: UUID) -> None:
        if not await self.repo.delete(medication_id, user_id):
            raise LookupError("Medication not found")
