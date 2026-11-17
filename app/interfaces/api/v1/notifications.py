from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.application.dto.notification_dto import NotificationListResponse, NotificationResponse
from app.application.dto.reminder_dto import RegisterDeviceRequest
from app.domain.entities.notification import Notification
from app.domain.value_objects.medication_enums import NotificationType
from app.interfaces.api.deps import (
    get_current_user, get_device_token_repository, get_notification_repository,
    get_push_service,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _to_response(n: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=n.id,
        type=n.type,
        title=n.title,
        body=n.body,
        data=n.data,
        created_at=n.created_at,
        read_at=n.read_at,
        is_read=n.read_at is not None,
    )


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="My notifications (dose reminders, refill reminders ...), newest first",
)
async def list_notifications(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
    repo=Depends(get_notification_repository),
):
    # One extra row tells us whether another page exists.
    rows = await repo.list_for_user(current_user.id, limit + 1, offset)
    return NotificationListResponse(
        items=[_to_response(n) for n in rows[:limit]],
        unread_count=await repo.count_unread(current_user.id),
        has_more=len(rows) > limit,
    )


@router.post(
    "/read-all",
    summary="Mark all my notifications as read",
)
async def mark_all_read(
    current_user=Depends(get_current_user),
    repo=Depends(get_notification_repository),
):
    return {"marked": await repo.mark_all_read(current_user.id)}


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark one notification as read",
)
async def mark_read(
    notification_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_notification_repository),
):
    if not await repo.mark_read(current_user.id, notification_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/devices",
    status_code=status.HTTP_201_CREATED,
    summary="Register this phone's FCM token (call after login and when the token refreshes)",
)
async def register_device(
    data: RegisterDeviceRequest,
    current_user=Depends(get_current_user),
    repo=Depends(get_device_token_repository),
):
    device = await repo.register(current_user.id, data.token, data.platform)
    return {"id": str(device.id), "platform": device.platform}


@router.delete(
    "/devices",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unregister a device token (call on logout)",
)
async def unregister_device(
    token: str = Query(..., description="The FCM token to remove"),
    current_user=Depends(get_current_user),
    repo=Depends(get_device_token_repository),
):
    await repo.remove(current_user.id, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test", summary="Send a test push to all my registered devices")
async def send_test_push(
    current_user=Depends(get_current_user),
    repo=Depends(get_device_token_repository),
    notification_repo=Depends(get_notification_repository),
    push=Depends(get_push_service),
):
    tokens = await repo.list_tokens(current_user.id)
    if not tokens:
        raise HTTPException(status_code=400, detail="No devices registered for this user")
    title, body = "Medisathi test", "Push notifications are working"
    try:
        invalid = await push.send(tokens, title, body, data={"type": "test"})
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Push service unavailable: {e}")
    await repo.remove_tokens(invalid)
    sent_to = len(tokens) - len(invalid)
    if sent_to:
        # Shown in the in-app list too, like every other push.
        await notification_repo.add(current_user.id, NotificationType.TEST, title, body)
    return {"sent_to": sent_to, "removed_invalid_tokens": len(invalid)}
