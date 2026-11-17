import asyncio
import logging
from typing import Dict, List, Optional

from firebase_admin import messaging

from app.application.interfaces.notification_service import PushNotificationService
from app.config import settings
from app.infrastructure.security.firebase_verifer import ensure_firebase_initialized

logger = logging.getLogger("uvicorn.error")

# FCM accepts at most 500 tokens per multicast call.
_BATCH_SIZE = 500
_DEAD_TOKEN_ERRORS = (messaging.UnregisteredError, messaging.SenderIdMismatchError)


class FCMPushNotifier(PushNotificationService):

    async def send(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        collapse_key: Optional[str] = None,
        android_channel_id: Optional[str] = None,
    ) -> List[str]:
        if not tokens:
            return []
        ensure_firebase_initialized()

        invalid: List[str] = []
        for i in range(0, len(tokens), _BATCH_SIZE):
            batch = tokens[i : i + _BATCH_SIZE]
            message = self._build(
                batch, title, body, data or {}, collapse_key,
                android_channel_id or settings.REMINDER_ANDROID_CHANNEL_ID,
            )
            response = await asyncio.to_thread(messaging.send_each_for_multicast, message)
            for token, result in zip(batch, response.responses):
                if result.success:
                    continue
                if isinstance(result.exception, _DEAD_TOKEN_ERRORS):
                    invalid.append(token)
                else:
                    logger.warning("FCM send failed: %s", result.exception)
        return invalid

    @staticmethod
    def _build(
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, str],
        collapse_key: Optional[str],
        android_channel_id: str,
    ) -> messaging.MulticastMessage:
        android = messaging.AndroidConfig(
            priority="high",
            collapse_key=collapse_key,
            notification=messaging.AndroidNotification(
                # Same tag as the app's local notification -> Android replaces it
                # instead of showing a duplicate.
                tag=collapse_key,
                channel_id=android_channel_id,
                sound="default",
            ),
        )
        apns_headers = {"apns-priority": "10"}
        if collapse_key:
            apns_headers["apns-collapse-id"] = collapse_key[:64]
        apns = messaging.APNSConfig(
            headers=apns_headers,
            payload=messaging.APNSPayload(aps=messaging.Aps(sound="default")),
        )
        return messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=title, body=body),
            data=data,
            android=android,
            apns=apns,
        )
