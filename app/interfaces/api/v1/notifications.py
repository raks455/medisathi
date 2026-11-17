from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.application.dto.reminder_dto import RegisterDeviceRequest
from app.interfaces.api.deps import (
    get_current_user, get_device_token_repository, get_push_service,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


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
    push=Depends(get_push_service),
):
    tokens = await repo.list_tokens(current_user.id)
    if not tokens:
        raise HTTPException(status_code=400, detail="No devices registered for this user")
    try:
        invalid = await push.send(
            tokens, "Medisathi test", "Push notifications are working", data={"type": "test"}
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Push service unavailable: {e}")
    await repo.remove_tokens(invalid)
    return {"sent_to": len(tokens) - len(invalid), "removed_invalid_tokens": len(invalid)}
