from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from app.domain.entities.medication import Medication


class MedicationRepository(ABC):

    @abstractmethod
    async def create(self, medication: Medication) -> Medication:
        pass

    @abstractmethod
    async def get_by_id(self, medication_id: UUID, user_id: UUID) -> Optional[Medication]:
        """Return the medication only if it belongs to the given user."""
        pass

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> List[Medication]:
        pass

    @abstractmethod
    async def update(self, medication: Medication) -> Medication:
        pass

    @abstractmethod
    async def delete(self, medication_id: UUID, user_id: UUID) -> bool:
        """Delete the medication; returns False if it did not exist for this user."""
        pass

    @abstractmethod
    async def list_with_active_reminders(self) -> List[Medication]:
        """All medications (any user) whose schedule has reminders enabled."""
        pass
