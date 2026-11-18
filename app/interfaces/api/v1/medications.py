from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.application.dto.medication_dto import (
    MedicationCreateRequest,
    MedicationResponse,
    MedicationUpdateRequest,
)
from app.application.use_cases.medication.manage_medications import (
    CreateMedicationUseCase,
    DeleteMedicationUseCase,
    GetMedicationUseCase,
    ListMedicationsUseCase,
    ResumeMedicationUseCase,
    StopMedicationUseCase,
    UpdateMedicationUseCase,
)
from app.domain.value_objects.medication_enums import AlertStyle, IntakeTiming, MedicineType
from app.config import settings
from app.infrastructure.security.photo_links import is_valid_signature
from app.interfaces.api.deps import get_current_user, get_medication_repository

router = APIRouter(prefix="/medications", tags=["Medications"])


def _not_found(e: LookupError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/options", summary="Allowed medicine types and intake timings")
async def get_options():
    return {
        "medicine_types": [t.value for t in MedicineType],
        "intake_timings": [t.value for t in IntakeTiming],
        "alert_styles": [s.value for s in AlertStyle],
    }


@router.post(
    "",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a medicine",
)
async def create_medication(
    data: MedicationCreateRequest,
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    med = await CreateMedicationUseCase(repo).execute(current_user.id, data)
    return MedicationResponse.from_entity(med)


@router.get("", response_model=List[MedicationResponse], summary="List my medicines")
async def list_medications(
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    meds = await ListMedicationsUseCase(repo).execute(current_user.id)
    return [MedicationResponse.from_entity(m) for m in meds]


@router.get("/{medication_id}", response_model=MedicationResponse, summary="Get one medicine")
async def get_medication(
    medication_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    try:
        med = await GetMedicationUseCase(repo).execute(current_user.id, medication_id)
    except LookupError as e:
        raise _not_found(e)
    return MedicationResponse.from_entity(med)


@router.patch("/{medication_id}", response_model=MedicationResponse, summary="Edit a medicine")
async def update_medication(
    medication_id: UUID,
    data: MedicationUpdateRequest,
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    try:
        med = await UpdateMedicationUseCase(repo).execute(current_user.id, medication_id, data)
    except LookupError as e:
        raise _not_found(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return MedicationResponse.from_entity(med)


@router.post(
    "/{medication_id}/stop",
    response_model=MedicationResponse,
    summary="Stop a medicine (no more doses or reminders; history is kept)",
)
async def stop_medication(
    medication_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    try:
        med = await StopMedicationUseCase(repo).execute(current_user.id, medication_id)
    except LookupError as e:
        raise _not_found(e)
    return MedicationResponse.from_entity(med)


@router.post(
    "/{medication_id}/resume",
    response_model=MedicationResponse,
    summary="Start a stopped medicine again",
)
async def resume_medication(
    medication_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    try:
        med = await ResumeMedicationUseCase(repo).execute(current_user.id, medication_id)
    except LookupError as e:
        raise _not_found(e)
    return MedicationResponse.from_entity(med)


@router.delete(
    "/{medication_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a medicine",
)
async def delete_medication(
    medication_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    try:
        await DeleteMedicationUseCase(repo).execute(current_user.id, medication_id)
    except LookupError as e:
        raise _not_found(e)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- photo of the medicine ----------------------------------------------

_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
# What the file really is, whatever the upload claims.
_PHOTO_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
}


def _photo_type(data: bytes) -> str | None:
    for magic, content_type in _PHOTO_SIGNATURES.items():
        if data.startswith(magic):
            return content_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.put(
    "/{medication_id}/photo",
    response_model=MedicationResponse,
    summary="Add or replace the photo of a medicine (JPEG, PNG or WebP)",
)
async def set_medication_photo(
    medication_id: UUID,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    if await repo.get_by_id(medication_id, current_user.id) is None:
        raise HTTPException(status_code=404, detail="Medication not found")
    limit = settings.MEDICINE_PHOTO_MAX_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"The photo is too large (max {settings.MEDICINE_PHOTO_MAX_MB} MB)")
    content_type = _photo_type(data)
    if content_type not in _PHOTO_TYPES:
        raise HTTPException(status_code=400, detail="The photo must be a JPEG, PNG or WebP image")
    await repo.set_photo(medication_id, data, content_type)
    return MedicationResponse.from_entity(await repo.get_by_id(medication_id, current_user.id))


@router.delete(
    "/{medication_id}/photo",
    response_model=MedicationResponse,
    summary="Remove the photo of a medicine",
)
async def delete_medication_photo(
    medication_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    if await repo.get_by_id(medication_id, current_user.id) is None:
        raise HTTPException(status_code=404, detail="Medication not found")
    await repo.delete_photo(medication_id)
    return MedicationResponse.from_entity(await repo.get_by_id(medication_id, current_user.id))


@router.get(
    "/{medication_id}/photo/{version}",
    summary="The photo itself. No token: the signed link from `photo_url` is the key",
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def get_medication_photo(
    medication_id: UUID,
    version: str,
    sig: str = Query(..., description="Signature from `photo_url`"),
    repo=Depends(get_medication_repository),
):
    not_found = HTTPException(status_code=404, detail="Photo not found")
    if not is_valid_signature(medication_id, version, sig):
        raise not_found
    photo = await repo.get_photo(medication_id, version)
    if photo is None:
        raise not_found
    data, content_type = photo
    # The link changes with the photo, so the picture can be cached for good.
    return Response(content=data, media_type=content_type,
                    headers={"Cache-Control": "private, max-age=31536000, immutable"})
