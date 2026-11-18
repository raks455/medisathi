from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from app.domain.value_objects.health_enums import RecordCategory, RecordFolder


@dataclass
class HealthRecord:
    """A stored document (prescription photo, lab report PDF ...). The file
    bytes are kept separately and only loaded on download."""
    id: UUID
    user_id: UUID
    folder: RecordFolder
    category: RecordCategory
    title: str
    file_name: str
    content_type: str
    size_bytes: int
    notes: Optional[str] = None
    document_date: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
