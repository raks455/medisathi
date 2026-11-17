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
    ) -> List[str]:
        """Send a push to the given device tokens.

        `collapse_key` makes the phone replace any notification with the same
        key instead of showing a second one.

        Returns the tokens that are no longer valid and should be deleted.
        """
        pass
