from datetime import datetime, timezone
from uuid import UUID
from app.application.dto.auth_dto import TokenResponse

class RefreshTokenUseCase:
    def __init__(self, user_repo, token_service, revoked_repo,
                 reuse_grace_seconds: int = 120):
        self.user_repo = user_repo
        self.token_service = token_service
        self.revoked_repo = revoked_repo
        self.reuse_grace_seconds = reuse_grace_seconds

    async def execute(self, refresh_token: str) -> TokenResponse:
        payload = self.token_service.decode_token(refresh_token, "refresh")
        if not payload:
            raise ValueError("Invalid or expired refresh token")
        if await self.revoked_repo.is_revoked(payload["jti"]):
            # Used once already. Normally that ends it, except just after the
            # exchange: the phone may not have received the new tokens.
            if not await self.revoked_repo.was_rotated_within(
                    payload["jti"], self.reuse_grace_seconds):
                raise ValueError("Invalid or expired refresh token")

        user_id = UUID(payload["sub"])
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise ValueError("Invalid refresh token")

        # rotation: the old refresh token can't be used again
        await self.revoked_repo.revoke(
            payload["jti"], user_id,
            datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            rotated=True,
        )

        return TokenResponse(
            access_token=self.token_service.create_access_token(user.id),
            refresh_token=self.token_service.create_refresh_token(user.id),
            user_id=str(user.id),
            email=user.email,
            full_name=user.full_name,
        )