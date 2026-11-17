from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.medication_enums import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: NotificationType
    title: str
    body: str
    data: Dict[str, str] = Field(
        default_factory=dict,
        description="Extra details, e.g. medication_id, dose_key, scheduled_for, days_left",
    )
    created_at: datetime
    read_at: Optional[datetime] = None
    is_read: bool = False


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    unread_count: int = Field(..., description="All unread notifications, not just this page")
    has_more: bool = Field(..., description="True if older notifications exist after this page")
