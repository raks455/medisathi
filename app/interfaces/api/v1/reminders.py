from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.dto.reminder_dto import (
    DoseLogResponse, DoseScheduleResponse, LogDoseRequest,
)
from app.application.use_cases.reminder.dose_schedule import (
    GetDoseScheduleUseCase, LogDoseUseCase,
)
from app.config import settings
from app.interfaces.api.deps import (
    get_current_user, get_dose_log_repository, get_medication_repository,
)

router = APIRouter(prefix="/reminders", tags=["Reminders"])


def _today(tz_name: str) -> date:
    try:
        return datetime.now(ZoneInfo(tz_name)).date()
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=400, detail=f"Unknown timezone '{tz_name}'")


@router.get(
    "/today",
    response_model=DoseScheduleResponse,
    summary="Today's doses with status (taken / skipped / missed / due / upcoming)",
)
async def get_today(
    tz: str = Query("Asia/Kathmandu", description="User's IANA timezone, decides what 'today' is"),
    current_user=Depends(get_current_user),
    med_repo=Depends(get_medication_repository),
    dose_repo=Depends(get_dose_log_repository),
):
    today = _today(tz)
    use_case = GetDoseScheduleUseCase(med_repo, dose_repo, settings.DOSE_MISSED_AFTER_MINUTES)
    return await use_case.execute(current_user.id, today, today)


@router.get(
    "/schedule",
    response_model=DoseScheduleResponse,
    summary="Doses for a date range (max 31 days) - use for history and adherence",
)
async def get_schedule(
    start_date: date,
    end_date: Optional[date] = None,
    current_user=Depends(get_current_user),
    med_repo=Depends(get_medication_repository),
    dose_repo=Depends(get_dose_log_repository),
):
    use_case = GetDoseScheduleUseCase(med_repo, dose_repo, settings.DOSE_MISSED_AFTER_MINUTES)
    try:
        return await use_case.execute(current_user.id, start_date, end_date or start_date)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/doses",
    response_model=DoseLogResponse,
    summary="Mark a dose as taken or skipped",
)
async def log_dose(
    data: LogDoseRequest,
    current_user=Depends(get_current_user),
    med_repo=Depends(get_medication_repository),
    dose_repo=Depends(get_dose_log_repository),
):
    try:
        return await LogDoseUseCase(med_repo, dose_repo).execute(current_user.id, data)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
