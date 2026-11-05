# app/application/use_cases/auth/google_login.py
from firebase_admin import auth as fb_auth
from app.application.dto.auth_dto import TokenResponse
# + your user repository / JWT service imports

class GoogleLoginUseCase:
    def __init__(self, user_repo, token_service):  # inject whatever you use
        self.user_repo = user_repo
        self.token_service = token_service

    async def execute(self, id_token: str) -> TokenResponse:
        try:
            # Verify the Google ID token with Firebase Admin
            decoded = fb_auth.verify_id_token(id_token)
        except Exception as e:
            raise ValueError("Invalid Google ID token") from e

        email = decoded.get("email")
        name = decoded.get("name")
        picture = decoded.get("picture")
        firebase_uid = decoded["uid"]

        if not email:
            raise ValueError("Google account has no email")

        # Find or create user in your DB
        user = await self.user_repo.get_by_email(email)
        if not user:
            user = await self.user_repo.create(
                email=email,
                full_name=name,
                avatar_url=picture,
                provider="google",
                provider_id=firebase_uid,
                # no password
            )
        else:
            # Optional: update avatar / name if changed
            pass

        # Issue your own access + refresh tokens
        access_token, refresh_token = await self.token_service.create_tokens(user)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            # + any other fields you have
        )