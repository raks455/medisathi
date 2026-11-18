"""Links to medicine photos that work without signing in.

A reminder push can carry a picture, but the phone's notification system
fetches it without the user's token. So the link is signed instead: it holds
an HMAC of the medicine id and photo version, which only this server can
produce. The version changes whenever the photo does, so an old link stops
working and a cached picture is never stale.
"""
import hashlib
import hmac
from typing import Optional
from uuid import UUID

from app.config import settings
from app.domain.entities.medication import Medication


def photo_signature(medication_id: UUID, version: str) -> str:
    message = f"medicine-photo:{medication_id}:{version}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()[:40]


def is_valid_signature(medication_id: UUID, version: str, signature: str) -> bool:
    return hmac.compare_digest(photo_signature(medication_id, version), signature)


def medicine_photo_url(med: Medication) -> Optional[str]:
    if not med.photo_version:
        return None
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return (f"{base}/api/v1/medications/{med.id}/photo/{med.photo_version}"
            f"?sig={photo_signature(med.id, med.photo_version)}")
