from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from app.domain.entities.device_token import DeviceToken


class DeviceTokenRepository(ABC):

    @abstractmethod
    async def register(self, user_id: UUID, token: str, platform: Optional[str]) -> DeviceToken:
        pass

    @abstractmethod
    async def remove(self, user_id: UUID, token: str) -> bool:
        pass

    @abstractmethod
    async def remove_tokens(self, tokens: List[str]) -> None:
        pass

    @abstractmethod
    async def list_tokens(self, user_id: UUID) -> List[str]:
        pass
