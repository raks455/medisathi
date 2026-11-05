import asyncio, json, os
import firebase_admin
from firebase_admin import auth as fb_auth, credentials


class FirebaseTokenVerifier:
    def _ensure_initialized(self) -> None:
        if firebase_admin._apps:
            return
        raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if not raw:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON is not set")
        firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))

    async def verify(self, id_token: str) -> dict:
        self._ensure_initialized()
        try:
            # verify_id_token is blocking, so run it off the event loop
            return await asyncio.to_thread(fb_auth.verify_id_token, id_token)
        except Exception:
            logger.warning("Firebase verify failed: %s: %s", type(e).__name__, e)
            raise ValueError("Invalid Google sign-in token")