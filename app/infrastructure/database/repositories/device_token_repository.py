import uuid
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.device_token import DeviceToken
from app.domain.repositories.device_token_repository import DeviceTokenRepository
from app.infrastructure.database.models.device_token import DeviceTokenModel


class SQLAlchemyDeviceTokenRepository(DeviceTokenRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register(self, user_id: UUID, token: str, platform: Optional[str]) -> DeviceToken:
        # A token belongs to one device; if another account logs in on that
        # device, the token moves to the new user.
        stmt = (
            insert(DeviceTokenModel)
            .values(id=uuid.uuid4(), user_id=user_id, token=token, platform=platform)
            .on_conflict_do_update(
                index_elements=[DeviceTokenModel.token],
                set_={"user_id": user_id, "platform": platform, "updated_at": func.now()},
            )
            .returning(DeviceTokenModel)
        )
        result = await self.session.execute(stmt, execution_options={"populate_existing": True})
        m = result.scalar_one()
        await self.session.commit()
        return DeviceToken(
            id=m.id, user_id=m.user_id, token=m.token, platform=m.platform, created_at=m.created_at
        )

    async def remove(self, user_id: UUID, token: str) -> bool:
        result = await self.session.execute(
            delete(DeviceTokenModel).where(
                DeviceTokenModel.user_id == user_id, DeviceTokenModel.token == token
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def remove_tokens(self, tokens: List[str]) -> None:
        if not tokens:
            return
        await self.session.execute(
            delete(DeviceTokenModel).where(DeviceTokenModel.token.in_(tokens))
        )
        await self.session.commit()

    async def list_tokens(self, user_id: UUID) -> List[str]:
        result = await self.session.execute(
            select(DeviceTokenModel.token).where(DeviceTokenModel.user_id == user_id)
        )
        return list(result.scalars().all())
