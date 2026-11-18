"""Period logging rules and pregnancy setup."""
from dataclasses import replace
from datetime import date, timedelta
from typing import Optional
from uuid import UUID, uuid4

from app.application.dto.health_dto import PeriodRequest, PregnancyRequest
from app.domain.entities.womens_health import CyclePeriod, Pregnancy
from app.domain.repositories.health_repositories import CycleRepository, PregnancyRepository
from app.domain.services import cycle_forecast
from app.domain.services.pregnancy_progress import (
    GESTATION_DAYS, due_date_from_lmp, lmp_from_due_date,
)

# Allow the user's "today" to be a day ahead of the server (time zones).
_FUTURE_TOLERANCE = timedelta(days=1)


def _effective_end(p: CyclePeriod, average_length: int) -> date:
    """An ongoing period is assumed to last the user's average length."""
    return p.end_date or p.start_date + timedelta(days=average_length - 1)


class SavePeriodUseCase:
    """Adds or edits a period.

    Periods may not overlap. Starting a new period while an older one is
    still open closes the older one automatically.
    """

    def __init__(self, repo: CycleRepository):
        self.repo = repo

    async def execute(self, user_id: UUID, data: PeriodRequest, today: date,
                      period_id: Optional[UUID] = None) -> CyclePeriod:
        if data.start_date > today + _FUTURE_TOLERANCE:
            raise ValueError("A period cannot start in the future")

        existing = await self.repo.list(user_id)
        if period_id is not None and not any(p.id == period_id for p in existing):
            raise LookupError("Period not found")
        others = [p for p in existing if p.id != period_id]

        average = cycle_forecast.average_period_length(
            [cycle_forecast.LoggedPeriod(p.start_date, p.end_date) for p in others])
        new_end = data.end_date or data.start_date
        for other in others:
            if other.start_date <= new_end and data.start_date <= _effective_end(other, average):
                raise ValueError(
                    f"This overlaps the period that started on {other.start_date.isoformat()}"
                )

        # Close an earlier period that was left open.
        for other in others:
            if other.end_date is None and other.start_date < data.start_date:
                guess = other.start_date + timedelta(days=average - 1)
                await self.repo.update(replace(
                    other, end_date=min(guess, data.start_date - timedelta(days=1))))

        period = CyclePeriod(
            id=period_id or uuid4(),
            user_id=user_id,
            start_date=data.start_date,
            end_date=data.end_date,
            flow=data.flow,
            notes=data.notes,
        )
        if period_id is None:
            return await self.repo.add(period)
        return await self.repo.update(period)


class SavePregnancyUseCase:
    def __init__(self, repo: PregnancyRepository):
        self.repo = repo

    async def execute(self, user_id: UUID, data: PregnancyRequest, today: date) -> Pregnancy:
        if data.last_period_date is not None:
            lmp = data.last_period_date
            due = due_date_from_lmp(lmp)
        else:
            due = data.due_date
            lmp = lmp_from_due_date(due)
        if lmp > today + _FUTURE_TOLERANCE:
            raise ValueError("The last period date cannot be in the future")
        if (today - lmp).days > GESTATION_DAYS + 42:
            raise ValueError("That date is too long ago for a current pregnancy")

        current = await self.repo.get_active(user_id)
        return await self.repo.save(Pregnancy(
            id=current.id if current else uuid4(),
            user_id=user_id,
            last_period_date=lmp,
            due_date=due,
            notes=data.notes,
        ))
