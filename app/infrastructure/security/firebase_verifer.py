import base64
import asyncio, json, logging
import firebase_admin
from firebase_admin import auth as fb_auth, credentials

from app.config import settings

logger = logging.getLogger("uvicorn.error")  # uvicorn always prints this one


class FirebaseTokenVerifier:
    def _ensure_initialized(self) -> None:
        if firebase_admin._apps:
            return
        if settings.FIREBASE_SERVICE_ACCOUNT_B64:
            info = json.loads(base64.b64decode(settings.FIREBASE_SERVICE_ACCOUNT_B64))
            cred = credentials.Certificate(info)
        elif settings.FIREBASE_SERVICE_ACCOUNT_FILE:
            cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_FILE)
        elif settings.FIREBASE_SERVICE_ACCOUNT_JSON:
            cred = credentials.Certificate(json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON))
        else:
            raise RuntimeError(
                "Set FIREBASE_SERVICE_ACCOUNT_B64, _FILE or _JSON"
            )
        firebase_admin.initialize_app(cred)
    
    async def verify(self, id_token: str) -> dict:
        try:
            self._ensure_initialized()
        except Exception:
            logger.exception("Firebase Admin is not configured correctly")
            raise RuntimeError("Google sign-in is not configured on the server")

        try:
            return await asyncio.to_thread(fb_auth.verify_id_token, id_token)
        except Exception as e:
            logger.warning("Firebase verify failed: %s: %s", type(e).__name__, e)
            raise ValueError("Invalid Google sign-in token")