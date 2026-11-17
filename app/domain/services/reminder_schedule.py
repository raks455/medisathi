"""Pure functions that expand a MedicationSchedule into concrete dose times."""
from datetime import date, datetime, timedelta, timezone
from typing import List
from zoneinfo import ZoneInfo

from app.domain.entities.medication import MedicationSchedule


def dose_key(medication_id, scheduled_for: datetime) -> str:
    """Stable id for one dose, shared by local notifications, pushes and dose logs.

    Format: "<medication_id>:<YYYYMMDDTHHMM UTC>"
    """
    utc = scheduled_for.astimezone(timezone.utc)
    return f"{medication_id}:{utc.strftime('%Y%m%dT%H%M')}"


def _is_active_on(schedule: MedicationSchedule, day: date) -> bool:
    if schedule.start_date and day < schedule.start_date:
        return False
    if schedule.end_date and day > schedule.end_date:
        return False
    if schedule.days_of_week is not None and day.weekday() not in schedule.days_of_week:
        return False
    return True


def occurrences_between(
    schedule: MedicationSchedule, start: datetime, end: datetime
) -> List[datetime]:
    """All dose times t with start <= t < end, returned as UTC datetimes (sorted).

    `start` and `end` must be timezone-aware.
    """
    tz = ZoneInfo(schedule.timezone)
    local_start = start.astimezone(tz).date() - timedelta(days=1)
    local_end = end.astimezone(tz).date() + timedelta(days=1)

    result: List[datetime] = []
    day = local_start
    while day <= local_end:
        if _is_active_on(schedule, day):
            for t in schedule.reminder_times:
                local_dt = datetime.combine(day, t.replace(second=0, microsecond=0), tzinfo=tz)
                utc_dt = local_dt.astimezone(timezone.utc)
                if start <= utc_dt < end:
                    result.append(utc_dt)
        day += timedelta(days=1)
    return sorted(set(result))


def occurrences_on_local_date(schedule: MedicationSchedule, day: date) -> List[datetime]:
    """Dose times (UTC) that fall on `day` in the schedule's own timezone."""
    tz = ZoneInfo(schedule.timezone)
    start = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    return occurrences_between(schedule, start, start + timedelta(days=1))


def is_scheduled_slot(schedule: MedicationSchedule, when: datetime) -> bool:
    when = when.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return when in occurrences_between(schedule, when, when + timedelta(minutes=1))
