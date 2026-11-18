from uuid import uuid4

from fastapi import APIRouter, Depends, status

from app.application.dto.health_dto import FeedbackRequest
from app.domain.entities.feedback import Feedback
from app.interfaces.api.deps import get_current_user, get_feedback_repository

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("", status_code=status.HTTP_201_CREATED, summary="Send feedback to the team")
async def send_feedback(
    data: FeedbackRequest,
    current_user=Depends(get_current_user),
    repo=Depends(get_feedback_repository),
):
    saved = await repo.add(Feedback(
        id=uuid4(),
        user_id=current_user.id,
        topic=data.topic,
        rating=data.rating,
        message=data.message,
        app_version=data.app_version,
        platform=data.platform,
    ))
    return {"id": str(saved.id), "received_at": saved.created_at}
