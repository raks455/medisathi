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
from app.infrastructure.database.repositories.medication_repository import SQLAlchemyMedicationRepository
from app.infrastructure.database.repositories.dose_log_repository import SQLAlchemyDoseLogRepository
from app.infrastructure.database.repositories.device_token_repository import SQLAlchemyDeviceTokenRepository
from app.infrastructure.database.repositories.notification_repository import SQLAlchemyNotificationRepository
from app.infrastructure.notifications.push_notifier import FCMPushNotifier

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

def get_medication_repository(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyMedicationRepository(session)


def get_dose_log_repository(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyDoseLogRepository(session)


def get_device_token_repository(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyDeviceTokenRepository(session)


def get_push_service() -> FCMPushNotifier:
    return FCMPushNotifier()


def get_notification_repository(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyNotificationRepository(session)


# ---- health records, vitals, mood, cycle, pregnancy, feedback ----

from app.infrastructure.database.repositories.health_repositories import (  # noqa: E402
    SQLAlchemyCycleRepository, SQLAlchemyFeedbackRepository,
    SQLAlchemyHealthRecordRepository, SQLAlchemyMoodRepository,
    SQLAlchemyPregnancyRepository, SQLAlchemyVitalRepository,
)


def get_health_record_repository(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyHealthRecordRepository(session)


def get_vital_repository(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyVitalRepository(session)


def get_mood_repository(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyMoodRepository(session)


def get_cycle_repository(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyCycleRepository(session)


def get_pregnancy_repository(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyPregnancyRepository(session)


def get_feedback_repository(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyFeedbackRepository(session)
