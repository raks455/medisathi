"""Repositories for health records, vitals, mood, cycle, pregnancy and feedback.

Every method is scoped to a user: a row belonging to someone else behaves as
if it does not exist.
"""
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID

from app.domain.entities.feedback import Feedback
from app.domain.entities.health_record import HealthRecord
from app.domain.entities.wellness import MoodEntry, VitalReading
from app.domain.entities.womens_health import CyclePeriod, CycleSettings, Pregnancy
from app.domain.value_objects.health_enums import RecordCategory, RecordFolder, VitalType


class HealthRecordRepository(ABC):
    @abstractmethod
    async def create(self, record: HealthRecord, data: bytes) -> HealthRecord: ...

    @abstractmethod
    async def list(self, user_id: UUID, folder: Optional[RecordFolder] = None,
                   category: Optional[RecordCategory] = None) -> List[HealthRecord]:
        """Newest first."""

    @abstractmethod
    async def get(self, user_id: UUID, record_id: UUID) -> Optional[HealthRecord]: ...

    @abstractmethod
    async def get_file(self, user_id: UUID, record_id: UUID) -> Optional[bytes]: ...

    @abstractmethod
    async def update(self, record: HealthRecord) -> HealthRecord: ...

    @abstractmethod
    async def delete(self, user_id: UUID, record_id: UUID) -> bool: ...

    @abstractmethod
    async def usage(self, user_id: UUID) -> Dict[str, Dict[str, int]]:
        """{folder: {"count": n, "bytes": n}} for every folder with files."""


class VitalRepository(ABC):
    @abstractmethod
    async def add(self, reading: VitalReading) -> VitalReading: ...

    @abstractmethod
    async def list(self, user_id: UUID, type: Optional[VitalType] = None,
                   since: Optional[datetime] = None, limit: int = 100) -> List[VitalReading]:
        """Newest first."""

    @abstractmethod
    async def latest(self, user_id: UUID, type: VitalType) -> Optional[VitalReading]: ...

    @abstractmethod
    async def delete(self, user_id: UUID, reading_id: UUID) -> bool: ...


class MoodRepository(ABC):
    @abstractmethod
    async def add(self, entry: MoodEntry) -> MoodEntry: ...

    @abstractmethod
    async def list(self, user_id: UUID, since: Optional[datetime] = None,
                   limit: int = 100) -> List[MoodEntry]:
        """Newest first."""

    @abstractmethod
    async def delete(self, user_id: UUID, entry_id: UUID) -> bool: ...


class CycleRepository(ABC):
    @abstractmethod
    async def add(self, period: CyclePeriod) -> CyclePeriod: ...

    @abstractmethod
    async def list(self, user_id: UUID) -> List[CyclePeriod]:
        """Newest first."""

    @abstractmethod
    async def get(self, user_id: UUID, period_id: UUID) -> Optional[CyclePeriod]: ...

    @abstractmethod
    async def update(self, period: CyclePeriod) -> CyclePeriod: ...

    @abstractmethod
    async def delete(self, user_id: UUID, period_id: UUID) -> bool: ...

    @abstractmethod
    async def get_settings(self, user_id: UUID) -> CycleSettings:
        """Defaults when the user has not saved any."""

    @abstractmethod
    async def save_settings(self, settings: CycleSettings) -> CycleSettings: ...

    @abstractmethod
    async def list_reminder_settings(self) -> List[CycleSettings]:
        """Users with any cycle reminder turned on."""

    @abstractmethod
    async def claim_alert(self, user_id: UUID, key: str) -> bool:
        """Records [key] as sent. False if it was already sent."""


class PregnancyRepository(ABC):
    @abstractmethod
    async def get_active(self, user_id: UUID) -> Optional[Pregnancy]: ...

    @abstractmethod
    async def save(self, pregnancy: Pregnancy) -> Pregnancy:
        """Insert or update."""

    @abstractmethod
    async def delete(self, user_id: UUID, pregnancy_id: UUID) -> bool: ...


class FeedbackRepository(ABC):
    @abstractmethod
    async def add(self, feedback: Feedback) -> Feedback: ...
