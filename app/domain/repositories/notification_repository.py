from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from uuid import UUID

from app.domain.entities.notification import Notification
from app.domain.value_objects.medication_enums import NotificationType


class NotificationRepository(ABC):

    @abstractmethod
    async def add(
        self,
        user_id: UUID,
        type: NotificationType,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Notification:
        pass

    @abstractmethod
    async def list_for_user(self, user_id: UUID, limit: int, offset: int) -> List[Notification]:
        """Newest first."""
        pass

    @abstractmethod
    async def count_unread(self, user_id: UUID) -> int:
        pass

    @abstractmethod
    async def mark_read(self, user_id: UUID, notification_id: UUID) -> bool:
        """Returns False if the notification does not exist for this user."""
        pass

    @abstractmethod
    async def mark_all_read(self, user_id: UUID) -> int:
        """Returns how many notifications were marked."""
        pass
