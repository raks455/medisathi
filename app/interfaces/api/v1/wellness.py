"""Vitals (weight, height, blood pressure) and mood check-ins."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.application.dto.health_dto import (
    MoodCreateRequest, MoodListResponse, MoodResponse, VitalCreateRequest, VitalResponse,
    VitalsSummary,
)
from app.domain.entities.wellness import MoodEntry, VitalReading
from app.domain.services import vitals as vital_rules
from app.domain.value_objects.health_enums import Mood, VitalType
from app.interfaces.api.deps import get_current_user, get_mood_repository, get_vital_repository

vitals_router = APIRouter(prefix="/vitals", tags=["Vitals"])
moods_router = APIRouter(prefix="/moods", tags=["Mood"])


# ---- vitals ---------------------------------------------------------------

@vitals_router.post("", response_model=VitalResponse, status_code=status.HTTP_201_CREATED,
                    summary="Log weight (kg), height (cm) or blood pressure (mmHg)")
async def add_vital(
    data: VitalCreateRequest,
    current_user=Depends(get_current_user),
    repo=Depends(get_vital_repository),
):
    reading = await repo.add(VitalReading(
        id=uuid4(),
        user_id=current_user.id,
        type=data.type,
        value=round(data.value, 1),
        value2=round(data.value2) if data.value2 is not None else None,
        pulse=data.pulse,
        note=data.note,
        recorded_at=data.recorded_at,
    ))
    return VitalResponse.from_entity(reading)


@vitals_router.get("", response_model=List[VitalResponse],
                   summary="My readings, newest first")
async def list_vitals(
    type: Optional[VitalType] = Query(None),
    days: Optional[int] = Query(None, ge=1, le=3660, description="Only the last N days"),
    limit: int = Query(200, ge=1, le=1000),
    current_user=Depends(get_current_user),
    repo=Depends(get_vital_repository),
):
    since = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    readings = await repo.list(current_user.id, type, since, limit)
    return [VitalResponse.from_entity(r) for r in readings]


@vitals_router.get("/summary", response_model=VitalsSummary,
                   summary="Latest weight, height and blood pressure, with BMI")
async def vitals_summary(
    current_user=Depends(get_current_user),
    repo=Depends(get_vital_repository),
):
    weight = await repo.latest(current_user.id, VitalType.WEIGHT)
    height = await repo.latest(current_user.id, VitalType.HEIGHT)
    bp = await repo.latest(current_user.id, VitalType.BLOOD_PRESSURE)
    result = VitalsSummary(
        weight=VitalResponse.from_entity(weight) if weight else None,
        height=VitalResponse.from_entity(height) if height else None,
        blood_pressure=VitalResponse.from_entity(bp) if bp else None,
    )
    if weight and height:
        result.bmi = vital_rules.bmi(weight.value, height.value)
        result.bmi_category = vital_rules.bmi_category(result.bmi)
    if weight:
        # The newest reading at least ~30 days older than the latest one.
        older = await repo.list(current_user.id, VitalType.WEIGHT,
                                since=weight.recorded_at - timedelta(days=60), limit=200)
        cutoff = weight.recorded_at - timedelta(days=30)
        baseline = next((r for r in older if r.recorded_at <= cutoff), None)
        if baseline:
            result.weight_change_30d = round(weight.value - baseline.value, 1)
    return result


@vitals_router.delete("/{reading_id}", status_code=status.HTTP_204_NO_CONTENT,
                      summary="Delete a reading")
async def delete_vital(
    reading_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_vital_repository),
):
    if not await repo.delete(current_user.id, reading_id):
        raise HTTPException(status_code=404, detail="Reading not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- mood -----------------------------------------------------------------

@moods_router.post("", response_model=MoodResponse, status_code=status.HTTP_201_CREATED,
                   summary="How are you feeling right now?")
async def add_mood(
    data: MoodCreateRequest,
    current_user=Depends(get_current_user),
    repo=Depends(get_mood_repository),
):
    entry = await repo.add(MoodEntry(
        id=uuid4(),
        user_id=current_user.id,
        mood=data.mood,
        note=data.note,
        tags=data.tags,
        recorded_at=datetime.now(timezone.utc),
    ))
    return MoodResponse.from_entity(entry)


@moods_router.get("", response_model=MoodListResponse,
                  summary="My check-ins from the last N days, newest first")
async def list_moods(
    days: int = Query(30, ge=1, le=366),
    current_user=Depends(get_current_user),
    repo=Depends(get_mood_repository),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    entries = await repo.list(current_user.id, since, limit=500)
    counts = Counter(e.mood for e in entries)
    return MoodListResponse(
        items=[MoodResponse.from_entity(e) for e in entries],
        counts={m: counts.get(m, 0) for m in Mood},
    )


@moods_router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT,
                     summary="Delete a check-in")
async def delete_mood(
    entry_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_mood_repository),
):
    if not await repo.delete(current_user.id, entry_id):
        raise HTTPException(status_code=404, detail="Check-in not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
