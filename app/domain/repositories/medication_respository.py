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

    @abstractmethod
    async def adjust_inventory(self, medication_id: UUID, delta: float) -> None:
        """Add `delta` units to the stock (negative to use some); never below 0.

        Does nothing if the medication has no inventory.
        """
        pass

    @abstractmethod
    async def list_with_refill_reminders(self) -> List[Medication]:
        """All medications (any user) that have a schedule and an inventory
        with refill reminders enabled."""
        pass

    @abstractmethod
    async def claim_refill_alert(self, medication_id: UUID, stage: str) -> bool:
        """Atomically record that the refill alert `stage` is being sent.

        Returns True only for the first caller, so each alert is sent once
        even with several server instances.
        """
        pass
