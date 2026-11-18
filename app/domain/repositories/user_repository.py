from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from app.domain.entities.user import User

class UserRepository(ABC):

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        pass

    @abstractmethod
    async def create(self, user: User) -> User:
        pass

    @abstractmethod
    async def update_full_name(self, user_id: UUID, full_name: str) -> None:
        pass

    @abstractmethod
    async def get_language(self, user_id: UUID) -> str:
        """Language of the user's notifications ('en' when unknown)."""
        pass

    @abstractmethod
    async def set_language(self, user_id: UUID, language: str) -> None:
        pass
