"""The signed-in user's profile: name and personal health details."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status

from app.application.dto.health_dto import (
    LanguageRequest, ProfileResponse, ProfileUpdateRequest,
)
from app.domain.entities.user_profile import UserProfile
from app.interfaces.api.deps import (
    get_current_user, get_user_profile_repository, get_user_repository,
)

router = APIRouter(prefix="/profile", tags=["Profile"])


def _response(user, full_name: str, profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        user_id=user.id,
        email=user.email,
        full_name=full_name,
        date_of_birth=profile.date_of_birth,
        age=profile.age(datetime.now(timezone.utc).date()),
        gender=profile.gender,
        blood_group=profile.blood_group,
        conditions=profile.conditions,
        allergies=profile.allergies,
        language=user.language,
    )


@router.get("", response_model=ProfileResponse, summary="My profile")
async def get_profile(
    current_user=Depends(get_current_user),
    repo=Depends(get_user_profile_repository),
):
    return _response(current_user, current_user.full_name, await repo.get(current_user.id))


@router.put("", response_model=ProfileResponse,
            summary="Save my name, date of birth, gender, blood group, diseases and allergies")
async def update_profile(
    data: ProfileUpdateRequest,
    current_user=Depends(get_current_user),
    repo=Depends(get_user_profile_repository),
    user_repo=Depends(get_user_repository),
):
    if data.full_name != current_user.full_name:
        await user_repo.update_full_name(current_user.id, data.full_name)
    profile = await repo.save(UserProfile(
        user_id=current_user.id,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        blood_group=data.blood_group,
        conditions=data.conditions,
        allergies=data.allergies,
    ))
    return _response(current_user, data.full_name, profile)


@router.put("/language", status_code=status.HTTP_204_NO_CONTENT,
            summary="Language of my reminders and notifications (en or ne)")
async def set_language(
    data: LanguageRequest,
    current_user=Depends(get_current_user),
    user_repo=Depends(get_user_repository),
):
    if data.language != current_user.language:
        await user_repo.set_language(current_user.id, data.language)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
