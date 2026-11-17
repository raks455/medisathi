import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.notification import Notification
from app.domain.repositories.notification_repository import NotificationRepository
from app.domain.value_objects.medication_enums import NotificationType
from app.infrastructure.database.models.notification import NotificationModel


class SQLAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(
        self,
        user_id: UUID,
        type: NotificationType,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Notification:
        model = NotificationModel(
            id=uuid.uuid4(),
            user_id=user_id,
            type=type.value,
            title=title,
            body=body,
            data=data or {},
            # Set here (not only by the server default) so the returned
            # entity has it without another query.
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def list_for_user(self, user_id: UUID, limit: int, offset: int) -> List[Notification]:
        result = await self.session.execute(
            select(NotificationModel)
            .where(NotificationModel.user_id == user_id)
            .order_by(NotificationModel.created_at.desc())
            .limit(limit)
            .offset(offset)
            .execution_options(populate_existing=True)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_unread(self, user_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(NotificationModel)
            .where(NotificationModel.user_id == user_id, NotificationModel.read_at.is_(None))
        )
        return result.scalar_one()

    async def mark_read(self, user_id: UUID, notification_id: UUID) -> bool:
        result = await self.session.execute(
            update(NotificationModel)
            .where(NotificationModel.id == notification_id, NotificationModel.user_id == user_id)
            # Keep the first time it was read.
            .values(read_at=func.coalesce(NotificationModel.read_at, func.now()))
        )
        await self.session.commit()
        return result.rowcount > 0

    async def mark_all_read(self, user_id: UUID) -> int:
        result = await self.session.execute(
            update(NotificationModel)
            .where(NotificationModel.user_id == user_id, NotificationModel.read_at.is_(None))
            .values(read_at=func.now())
        )
        await self.session.commit()
        return result.rowcount

    @staticmethod
    def _to_entity(m: NotificationModel) -> Notification:
        return Notification(
            id=m.id,
            user_id=m.user_id,
            type=NotificationType(m.type),
            title=m.title,
            body=m.body,
            data=m.data or {},
            created_at=m.created_at,
            read_at=m.read_at,
        )
