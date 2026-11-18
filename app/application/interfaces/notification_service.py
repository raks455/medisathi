from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class PushNotificationService(ABC):

    @abstractmethod
    async def send(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        collapse_key: Optional[str] = None,
        android_channel_id: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> List[str]:
        """Send a push to the given device tokens.

        `collapse_key` makes the phone replace any notification with the same
        key instead of showing a second one. `android_channel_id` picks the
        Android notification channel (sound / importance); None = the default
        reminder channel. `image_url` is a picture shown in the notification
        (it must be reachable without signing in).

        Returns the tokens that are no longer valid and should be deleted.
        """
        pass
