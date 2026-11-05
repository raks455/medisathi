from fastapi import APIRouter, Depends, HTTPException, status,Response
from app.application.dto.auth_dto import RefreshRequest, RegisterRequest, LoginRequest, TokenResponse,GoogleLoginRequest
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.application.use_cases.auth.login_user import LoginUserUseCase
from fastapi.security import HTTPAuthorizationCredentials
from app.application.use_cases.auth.logout_user import LogoutUserUseCase
from app.interfaces.api.deps import get_register_use_case, get_login_use_case, get_refresh_use_case,get_logout_use_case, optional_bearer,get_google_login_use_case
from app.application.use_cases.auth.refresh_token import RefreshTokenUseCase
from app.application.use_cases.auth.google_login import GoogleLoginUseCase
from firebase_admin import auth as fb_auth, credentials
from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/auth", tags=["Authentication"])
@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    data: RegisterRequest,
    use_case: RegisterUserUseCase = Depends(get_register_use_case),
):
    try:
        return await use_case.execute(data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login user",
)
async def login(
    data: LoginRequest,
    use_case: LoginUserUseCase = Depends(get_login_use_case),
):
    try:
        return await use_case.execute(data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
        

@router.post("/refresh", response_model=TokenResponse, summary="Get a new access token")
async def refresh(
    data: RefreshRequest,
    use_case: RefreshTokenUseCase = Depends(get_refresh_use_case),
):
    try:
        return await use_case.execute(data.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
        
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Logout user")
async def logout(
    data: RefreshRequest,
    creds: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    use_case: LogoutUserUseCase = Depends(get_logout_use_case),
):
    await use_case.execute(data.refresh_token, creds.credentials if creds else None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/google", response_model=TokenResponse, summary="Login or register with Google")
async def google_login(
    data: GoogleLoginRequest,
    use_case: GoogleLoginUseCase = Depends(get_google_login_use_case),
):
    try:
        return await use_case.execute(data.id_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )