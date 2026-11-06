from fastapi import Depends,HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.session import get_db
from app.infrastructure.database.repositories.user_repository import SQLAlchemyUserRepository
from app.infrastructure.security.password_hasher import BcryptPasswordService
from app.infrastructure.security.jwt_service import JWTTokenService
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.application.use_cases.auth.login_user import LoginUserUseCase
from app.application.use_cases.auth.google_login import GoogleLoginUseCase
from app.application.use_cases.auth.refresh_token import RefreshTokenUseCase
from uuid import UUID
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.infrastructure.database.repositories.revoked_tokens_repository import SQLAlchemyRevokedTokenRepository
from app.application.use_cases.auth.logout_user import LogoutUserUseCase
from app.infrastructure.security.firebase_verifer import FirebaseTokenVerifier

bearer_scheme = HTTPBearer()
optional_bearer = HTTPBearer(auto_error=False)

def get_user_repository(session: AsyncSession = Depends(get_db)) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(session)

def get_password_service() -> BcryptPasswordService:
    return BcryptPasswordService()

def get_token_service() -> JWTTokenService:
    return JWTTokenService()

def get_register_use_case(
    user_repo=Depends(get_user_repository),
    password_service=Depends(get_password_service),
    token_service=Depends(get_token_service),
) -> RegisterUserUseCase:
    return RegisterUserUseCase(user_repo, password_service, token_service)

def get_login_use_case(
    user_repo=Depends(get_user_repository),
    password_service=Depends(get_password_service),
    token_service=Depends(get_token_service),
) -> LoginUserUseCase:
    return LoginUserUseCase(user_repo, password_service, token_service)

def get_revoked_repository(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyRevokedTokenRepository(session)

def get_refresh_use_case(
    user_repo=Depends(get_user_repository),
    token_service=Depends(get_token_service),
    revoked_repo=Depends(get_revoked_repository),
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(user_repo, token_service, revoked_repo)

def get_logout_use_case(
    token_service=Depends(get_token_service),
    revoked_repo=Depends(get_revoked_repository),
) -> LogoutUserUseCase:
    return LogoutUserUseCase(token_service, revoked_repo)

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    token_service=Depends(get_token_service),
    user_repo=Depends(get_user_repository),
    revoked_repo=Depends(get_revoked_repository),
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = token_service.decode_token(creds.credentials, "access")
    if not payload or await revoked_repo.is_revoked(payload["jti"]):
        raise unauthorized
    user = await user_repo.get_by_id(UUID(payload["sub"]))
    if not user or not user.is_active:
        raise unauthorized
    return user


def get_firebase_verifier() -> FirebaseTokenVerifier:
    return FirebaseTokenVerifier()

def get_google_login_use_case(
    user_repo=Depends(get_user_repository),
    token_service=Depends(get_token_service),
    verifier=Depends(get_firebase_verifier),
) -> GoogleLoginUseCase:
    return GoogleLoginUseCase(user_repo, token_service, verifier)