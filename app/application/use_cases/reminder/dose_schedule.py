from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from app.application.dto.reminder_dto import (
    AdherenceSummary, DoseLogResponse, DoseScheduleResponse, LogDoseRequest, ScheduledDose,
)
from app.domain.entities.dose_log import DoseLog
from app.domain.repositories.dose_log_repository import DoseLogRepository
from app.domain.repositories.medication_respository import MedicationRepository
from app.domain.services.reminder_schedule import (
    dose_key, is_scheduled_slot, occurrences_on_local_date,
)
from app.domain.value_objects.medication_enums import DoseStatus, DoseViewStatus

MAX_RANGE_DAYS = 31


class GetDoseScheduleUseCase:
    """Expand every medication schedule into doses for a date range, with status."""

    def __init__(
        self,
        med_repo: MedicationRepository,
        dose_repo: DoseLogRepository,
        missed_after_minutes: int,
    ):
        self.med_repo = med_repo
        self.dose_repo = dose_repo
        self.missed_after = timedelta(minutes=missed_after_minutes)

    async def execute(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
        now: Optional[datetime] = None,
    ) -> DoseScheduleResponse:
        if end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        if (end_date - start_date).days + 1 > MAX_RANGE_DAYS:
            raise ValueError(f"Date range can be at most {MAX_RANGE_DAYS} days")
        now = now or datetime.now(timezone.utc)

        meds = [m for m in await self.med_repo.list_by_user(user_id) if m.schedule]

        # Local dates differ per timezone, so pad the UTC query by a day each side.
        utc_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=1)
        utc_end = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=2)
        logs: Dict[Tuple[UUID, datetime], DoseLog] = {
            (log.medication_id, log.scheduled_for.astimezone(timezone.utc)): log
            for log in await self.dose_repo.list_for_user(user_id, utc_start, utc_end)
        }

        doses = []
        for med in meds:
            tz = ZoneInfo(med.schedule.timezone)
            # Doses scheduled before the medicine was added are not shown,
            # otherwise they would all count as "missed".
            added_at = med.created_at.replace(second=0, microsecond=0) if med.created_at else None
            day = start_date
            while day <= end_date:
                for when in occurrences_on_local_date(med.schedule, day):
                    log = logs.get((med.id, when))
                    if added_at and when < added_at and not log:
                        continue
                    # No dose is expected while the medicine is stopped.
                    if med.was_paused_at(when) and not log:
                        continue
                    local = when.astimezone(tz)
                    doses.append(
                        ScheduledDose(
                            dose_key=dose_key(med.id, when),
                            medication_id=med.id,
                            medication_name=med.name,
                            medicine_type=med.medicine_type,
                            dose=med.dose,
                            intake_timing=med.intake_timing,
                            instructions=med.instructions,
                            scheduled_for=when,
                            local_date=local.date(),
                            local_time=local.strftime("%H:%M"),
                            timezone=med.schedule.timezone,
                            status=self._status(when, log, now),
                            responded_at=log.responded_at if log else None,
                        )
                    )
                day += timedelta(days=1)

        doses.sort(key=lambda d: (d.scheduled_for, d.medication_name))
        return DoseScheduleResponse(
            start_date=start_date,
            end_date=end_date,
            summary=self._summary(doses),
            doses=doses,
        )

    def _status(self, when: datetime, log: Optional[DoseLog], now: datetime) -> DoseViewStatus:
        if log and log.status == DoseStatus.TAKEN:
            return DoseViewStatus.TAKEN
        if log and log.status == DoseStatus.SKIPPED:
            return DoseViewStatus.SKIPPED
        if now < when:
            return DoseViewStatus.UPCOMING
        if now < when + self.missed_after:
            return DoseViewStatus.DUE
        return DoseViewStatus.MISSED

    @staticmethod
    def _summary(doses) -> AdherenceSummary:
        counts = {s: 0 for s in DoseViewStatus}
        for d in doses:
            counts[d.status] += 1
        past = counts[DoseViewStatus.TAKEN] + counts[DoseViewStatus.SKIPPED] + counts[DoseViewStatus.MISSED]
        return AdherenceSummary(
            total=len(doses),
            taken=counts[DoseViewStatus.TAKEN],
            skipped=counts[DoseViewStatus.SKIPPED],
            missed=counts[DoseViewStatus.MISSED],
            due=counts[DoseViewStatus.DUE],
            upcoming=counts[DoseViewStatus.UPCOMING],
            adherence_percent=round(100 * counts[DoseViewStatus.TAKEN] / past, 1) if past else None,
        )


class LogDoseUseCase:
    """Mark a scheduled dose as taken or skipped (calling again changes the answer)."""

    def __init__(self, med_repo: MedicationRepository, dose_repo: DoseLogRepository):
        self.med_repo = med_repo
        self.dose_repo = dose_repo

    async def execute(self, user_id: UUID, data: LogDoseRequest) -> DoseLogResponse:
        med = await self.med_repo.get_by_id(data.medication_id, user_id)
        if not med:
            raise LookupError("Medication not found")
        if not med.schedule:
            raise ValueError("This medication has no reminder schedule")

        when = data.scheduled_for.astimezone(timezone.utc).replace(second=0, microsecond=0)
        if not is_scheduled_slot(med.schedule, when):
            raise ValueError("scheduled_for does not match a scheduled dose of this medication")

        new_status = DoseStatus(data.status)
        previous = await self.dose_repo.get(med.id, when)
        log = await self.dose_repo.upsert_status(user_id, med.id, when, new_status)

        # Keep the stock in step: taking a dose uses it up, and changing a
        # "taken" answer to "skipped" puts it back.
        if med.inventory:
            was_taken = previous is not None and previous.status == DoseStatus.TAKEN
            is_taken = new_status == DoseStatus.TAKEN
            if is_taken and not was_taken:
                await self.med_repo.adjust_inventory(med.id, -med.inventory.units_per_dose)
            elif was_taken and not is_taken:
                await self.med_repo.adjust_inventory(med.id, med.inventory.units_per_dose)
        return DoseLogResponse(
            id=log.id,
            dose_key=dose_key(med.id, log.scheduled_for),
            medication_id=log.medication_id,
            scheduled_for=log.scheduled_for,
            status=log.status.value,
            responded_at=log.responded_at,
        )
