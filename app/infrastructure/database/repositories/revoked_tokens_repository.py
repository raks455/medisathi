from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.models.revoked_token import RevokedTokenModel

class SQLAlchemyRevokedTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_revoked(self, jti: str) -> bool:
        return await self.session.get(RevokedTokenModel, jti) is not None

    async def revoke(self, jti: str, user_id: UUID, expires_at: datetime,
                     rotated: bool = False) -> None:
        """`rotated`: the token was exchanged for a new one, not signed out."""
        if await self.is_revoked(jti):
            return
        self.session.add(RevokedTokenModel(
            jti=jti, user_id=user_id, expires_at=expires_at,
            rotated_at=datetime.now(timezone.utc) if rotated else None,
        ))
        await self.session.commit()

    async def was_rotated_within(self, jti: str, seconds: int) -> bool:
        """True if the token was exchanged (not signed out) this recently."""
        row = await self.session.get(RevokedTokenModel, jti)
        if row is None or row.rotated_at is None:
            return False
        return datetime.now(timezone.utc) - row.rotated_at <= timedelta(seconds=seconds)