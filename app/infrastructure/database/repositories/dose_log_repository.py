import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.dose_log import DoseLog
from app.domain.repositories.dose_log_repository import DoseLogRepository
from app.domain.value_objects.medication_enums import DoseStatus
from app.infrastructure.database.models.medication import DoseLogModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SQLAlchemyDoseLogRepository(DoseLogRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_status(
        self, user_id: UUID, medication_id: UUID, scheduled_for: datetime, status: DoseStatus
    ) -> DoseLog:
        now = _now()
        stmt = (
            insert(DoseLogModel)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                medication_id=medication_id,
                scheduled_for=scheduled_for,
                status=status.value,
                responded_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_dose_logs_med_time",
                set_={"status": status.value, "responded_at": now},
            )
            .returning(DoseLogModel)
        )
        result = await self.session.execute(stmt, execution_options={"populate_existing": True})
        model = result.scalar_one()
        await self.session.commit()
        return self._to_entity(model)

    async def claim_for_notification(
        self, user_id: UUID, medication_id: UUID, scheduled_for: datetime
    ) -> bool:
        stmt = (
            insert(DoseLogModel)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                medication_id=medication_id,
                scheduled_for=scheduled_for,
                status=DoseStatus.PENDING.value,
                notified_at=_now(),
            )
            .on_conflict_do_nothing(constraint="uq_dose_logs_med_time")
            .returning(DoseLogModel.id)
        )
        result = await self.session.execute(stmt)
        claimed = result.scalar_one_or_none() is not None
        await self.session.commit()
        return claimed

    async def list_for_user(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        medication_id: Optional[UUID] = None,
    ) -> List[DoseLog]:
        query = select(DoseLogModel).where(
            DoseLogModel.user_id == user_id,
            DoseLogModel.scheduled_for >= start,
            DoseLogModel.scheduled_for < end,
        )
        if medication_id:
            query = query.where(DoseLogModel.medication_id == medication_id)
        result = await self.session.execute(query.order_by(DoseLogModel.scheduled_for))
        return [self._to_entity(m) for m in result.scalars().all()]

    @staticmethod
    def _to_entity(m: DoseLogModel) -> DoseLog:
        return DoseLog(
            id=m.id,
            user_id=m.user_id,
            medication_id=m.medication_id,
            scheduled_for=m.scheduled_for,
            status=DoseStatus(m.status),
            responded_at=m.responded_at,
            notified_at=m.notified_at,
        )
