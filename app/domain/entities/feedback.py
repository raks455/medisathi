from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.domain.value_objects.health_enums import FeedbackTopic


@dataclass
class Feedback:
    id: UUID
    user_id: UUID
    topic: FeedbackTopic
    message: str
    rating: Optional[int] = None
    app_version: Optional[str] = None
    platform: Optional[str] = None
    created_at: Optional[datetime] = None
