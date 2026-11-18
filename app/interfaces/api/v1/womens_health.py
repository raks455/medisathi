"""Period tracker and pregnancy tracker.

Endpoints that depend on "today" take an optional `today` query parameter:
the phone's local date, so predictions match the user's calendar. Without it
the server's UTC date is used.
"""
from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.application.dto.health_dto import (
    CycleOverviewResponse, CycleSettingsRequest, CycleSettingsResponse,
    CycleWindowResponse, PeriodRequest, PeriodResponse,
    PregnancyRequest, PregnancyResponse, PregnancyStatusResponse,
)
from app.application.use_cases.health.womens_health import (
    SavePeriodUseCase, SavePregnancyUseCase,
)
from app.domain.entities.womens_health import Pregnancy
from app.domain.services import cycle_forecast
from app.domain.services.pregnancy_progress import progress
from app.interfaces.api.deps import (
    get_current_user, get_cycle_repository, get_pregnancy_repository,
)

cycles_router = APIRouter(prefix="/cycles", tags=["Period tracker"])
pregnancy_router = APIRouter(prefix="/pregnancy", tags=["Pregnancy tracker"])

_TODAY = Query(None, description="The phone's local date (YYYY-MM-DD)")


def _today(value: Optional[date]) -> date:
    return value or datetime.now(timezone.utc).date()


_TZ = Query(None, description="The phone's IANA timezone, used for period reminders")


async def _sync_timezone(repo, user_id, tz: Optional[str]) -> None:
    """Remembers the phone's timezone so reminders arrive in the morning.

    Creates the settings row (reminders on by default) the first time."""
    if not tz:
        return
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return
    current = await repo.get_settings(user_id)
    if current.timezone != tz or current.alert_key is None:
        await repo.save_settings(replace(current, timezone=tz))


def _settings_response(s) -> CycleSettingsResponse:
    return CycleSettingsResponse(
        timezone=s.timezone,
        period_reminders=s.period_reminders,
        remind_days_before=s.remind_days_before,
        fertile_reminders=s.fertile_reminders,
    )


@cycles_router.get("/settings", response_model=CycleSettingsResponse,
                   summary="Period reminder settings")
async def get_cycle_settings(
    current_user=Depends(get_current_user),
    repo=Depends(get_cycle_repository),
):
    return _settings_response(await repo.get_settings(current_user.id))


@cycles_router.put("/settings", response_model=CycleSettingsResponse,
                   summary="Change period reminder settings (only the fields given)")
async def save_cycle_settings(
    data: CycleSettingsRequest,
    current_user=Depends(get_current_user),
    repo=Depends(get_cycle_repository),
):
    current = await repo.get_settings(current_user.id)
    changes = {k: v for k, v in data.model_dump().items() if v is not None}
    return _settings_response(await repo.save_settings(replace(current, **changes)))


# ---- periods --------------------------------------------------------------

@cycles_router.get("/overview", response_model=CycleOverviewResponse,
                   summary="Averages, cycle day, predictions and all logged periods")
async def cycle_overview(
    today: Optional[date] = _TODAY,
    cycles_ahead: int = Query(3, ge=1, le=12),
    tz: Optional[str] = _TZ,
    current_user=Depends(get_current_user),
    repo=Depends(get_cycle_repository),
):
    periods = await repo.list(current_user.id)
    if periods:
        await _sync_timezone(repo, current_user.id, tz)
    result = cycle_forecast.forecast(
        [cycle_forecast.LoggedPeriod(p.start_date, p.end_date) for p in periods],
        _today(today),
        cycles_ahead,
    )
    return CycleOverviewResponse(
        average_cycle_length=result.average_cycle_length,
        average_period_length=result.average_period_length,
        cycles_logged=result.cycles_logged,
        last_period_start=result.last_period_start,
        next_period_start=result.next_period_start,
        days_until_next_period=result.days_until_next_period,
        cycle_day=result.cycle_day,
        phase=result.phase,
        windows=[CycleWindowResponse(**w.__dict__) for w in result.windows],
        periods=[PeriodResponse.from_entity(p) for p in periods],
    )


@cycles_router.post("/periods", response_model=PeriodResponse,
                    status_code=status.HTTP_201_CREATED, summary="Log a period")
async def add_period(
    data: PeriodRequest,
    today: Optional[date] = _TODAY,
    tz: Optional[str] = _TZ,
    current_user=Depends(get_current_user),
    repo=Depends(get_cycle_repository),
):
    await _sync_timezone(repo, current_user.id, tz)
    try:
        period = await SavePeriodUseCase(repo).execute(current_user.id, data, _today(today))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return PeriodResponse.from_entity(period)


@cycles_router.put("/periods/{period_id}", response_model=PeriodResponse,
                   summary="Edit a period (e.g. set its end date)")
async def update_period(
    period_id: UUID,
    data: PeriodRequest,
    today: Optional[date] = _TODAY,
    current_user=Depends(get_current_user),
    repo=Depends(get_cycle_repository),
):
    try:
        period = await SavePeriodUseCase(repo).execute(
            current_user.id, data, _today(today), period_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return PeriodResponse.from_entity(period)


@cycles_router.delete("/periods/{period_id}", status_code=status.HTTP_204_NO_CONTENT,
                      summary="Delete a period")
async def delete_period(
    period_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_cycle_repository),
):
    if not await repo.delete(current_user.id, period_id):
        raise HTTPException(status_code=404, detail="Period not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- pregnancy ------------------------------------------------------------

def _pregnancy_response(p: Pregnancy, today: date) -> PregnancyResponse:
    info = progress(p.last_period_date, p.due_date, today)
    return PregnancyResponse(
        id=p.id,
        last_period_date=p.last_period_date,
        due_date=p.due_date,
        notes=p.notes,
        **info.__dict__,
    )


@pregnancy_router.get("", response_model=PregnancyStatusResponse,
                      summary="My tracked pregnancy with weekly progress (null if none)")
async def get_pregnancy(
    today: Optional[date] = _TODAY,
    current_user=Depends(get_current_user),
    repo=Depends(get_pregnancy_repository),
):
    pregnancy = await repo.get_active(current_user.id)
    return PregnancyStatusResponse(
        pregnancy=_pregnancy_response(pregnancy, _today(today)) if pregnancy else None)


@pregnancy_router.put("", response_model=PregnancyResponse,
                      summary="Start or update tracking from the last period or the due date")
async def save_pregnancy(
    data: PregnancyRequest,
    today: Optional[date] = _TODAY,
    current_user=Depends(get_current_user),
    repo=Depends(get_pregnancy_repository),
):
    day = _today(today)
    try:
        pregnancy = await SavePregnancyUseCase(repo).execute(current_user.id, data, day)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _pregnancy_response(pregnancy, day)


@pregnancy_router.delete("", status_code=status.HTTP_204_NO_CONTENT,
                         summary="Stop tracking the pregnancy")
async def delete_pregnancy(
    current_user=Depends(get_current_user),
    repo=Depends(get_pregnancy_repository),
):
    pregnancy = await repo.get_active(current_user.id)
    if not pregnancy:
        raise HTTPException(status_code=404, detail="No pregnancy is being tracked")
    await repo.delete(current_user.id, pregnancy.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
