from uuid import uuid4

from app.application.dto.auth_dto import TokenResponse
from app.domain.entities.user import User


class GoogleLoginUseCase:
    def __init__(self, user_repo, token_service, verifier):
        self.user_repo = user_repo
        self.token_service = token_service
        self.verifier = verifier

    async def execute(self, id_token: str) -> TokenResponse:
        claims = await self.verifier.verify(id_token)  # raises ValueError if invalid

        email = (claims.get("email") or "").strip().lower()
        if not email:
            raise ValueError("Google account has no email")
        if not claims.get("email_verified"):
            raise ValueError("Google email is not verified")

        user = await self.user_repo.get_by_email(email)
        if user is None:
            user = await self.user_repo.create(
                User(
                    id=uuid4(),
                    email=email,
                    full_name=(claims.get("name") or email.split("@")[0]).strip(),
                    hashed_password=None,
                )
            )
        if not user.is_active:
            raise ValueError("Account is inactive")

        return TokenResponse(
            access_token=self.token_service.create_access_token(user.id),
            refresh_token=self.token_service.create_refresh_token(user.id),
            user_id=str(user.id),
            email=user.email,
            full_name=user.full_name,
        )