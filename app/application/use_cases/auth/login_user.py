from app.domain.repositories.user_repository import UserRepository
from app.application.interfaces.password_services import PasswordService
from app.application.interfaces.token_service import TokenService
from app.application.dto.auth_dto import LoginRequest, TokenResponse

class LoginUserUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        password_service: PasswordService,
        token_service: TokenService,
    ):
        self.user_repo = user_repo
        self.password_service = password_service
        self.token_service = token_service

    async def execute(self, data: LoginRequest) -> TokenResponse:
        user = await self.user_repo.get_by_email(data.email.lower())
        if not user:
            raise ValueError("Invalid email or password")
        if not user.hashed_password:   # use your real field name
          raise ValueError("This account uses Google sign-in")
        if not self.password_service.verify_password(data.password, user.hashed_password):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is inactive")

        access_token = self.token_service.create_access_token(user.id)
        refresh_token = self.token_service.create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=str(user.id),
            email=user.email,
            full_name=user.full_name,
        )