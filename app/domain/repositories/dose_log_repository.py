from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.domain.entities.dose_log import DoseLog
from app.domain.value_objects.medication_enums import DoseStatus


class DoseLogRepository(ABC):

    @abstractmethod
    async def upsert_status(
        self, user_id: UUID, medication_id: UUID, scheduled_for: datetime, status: DoseStatus
    ) -> DoseLog:
        pass

    @abstractmethod
    async def claim_for_notification(
        self, user_id: UUID, medication_id: UUID, scheduled_for: datetime
    ) -> bool:
        """Atomically create a PENDING log for this dose.

        Returns True only if no log existed yet (so exactly one server
        instance sends the push, and doses already marked taken are skipped).
        """
        pass

    @abstractmethod
    async def list_for_user(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        medication_id: Optional[UUID] = None,
    ) -> List[DoseLog]:
        pass

    @abstractmethod
    async def get(self, medication_id: UUID, scheduled_for: datetime) -> Optional[DoseLog]:
        pass
