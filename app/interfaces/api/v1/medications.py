from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

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
    UpdateMedicationUseCase,
)
from app.domain.value_objects.medication_enums import IntakeTiming, MedicineType
from app.interfaces.api.deps import get_current_user, get_medication_repository

router = APIRouter(prefix="/medications", tags=["Medications"])


def _not_found(e: LookupError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/options", summary="Allowed medicine types and intake timings")
async def get_options():
    return {
        "medicine_types": [t.value for t in MedicineType],
        "intake_timings": [t.value for t in IntakeTiming],
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
    return await CreateMedicationUseCase(repo).execute(current_user.id, data)


@router.get("", response_model=List[MedicationResponse], summary="List my medicines")
async def list_medications(
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    return await ListMedicationsUseCase(repo).execute(current_user.id)


@router.get("/{medication_id}", response_model=MedicationResponse, summary="Get one medicine")
async def get_medication(
    medication_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    try:
        return await GetMedicationUseCase(repo).execute(current_user.id, medication_id)
    except LookupError as e:
        raise _not_found(e)


@router.patch("/{medication_id}", response_model=MedicationResponse, summary="Edit a medicine")
async def update_medication(
    medication_id: UUID,
    data: MedicationUpdateRequest,
    current_user=Depends(get_current_user),
    repo=Depends(get_medication_repository),
):
    try:
        return await UpdateMedicationUseCase(repo).execute(current_user.id, medication_id, data)
    except LookupError as e:
        raise _not_found(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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
