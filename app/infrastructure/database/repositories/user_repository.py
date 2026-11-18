from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.domain.entities.user import User
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.database.models.user import UserModel

class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def create(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            hashed_password=user.hashed_password,
            is_active=user.is_active,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def update_full_name(self, user_id: UUID, full_name: str) -> None:
        await self.session.execute(
            update(UserModel).where(UserModel.id == user_id).values(full_name=full_name)
        )
        await self.session.commit()

    async def get_language(self, user_id: UUID) -> str:
        result = await self.session.execute(
            select(UserModel.language).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none() or "en"

    async def set_language(self, user_id: UUID, language: str) -> None:
        await self.session.execute(
            update(UserModel).where(UserModel.id == user_id).values(language=language)
        )
        await self.session.commit()

    def _to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            full_name=model.full_name,
            hashed_password=model.hashed_password,
            is_active=model.is_active,
            language=model.language or "en",
            created_at=model.created_at,
            updated_at=model.updated_at,
        )