import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.application.interfaces.notification_service import PushNotificationService
from app.domain.entities.medication import Medication
from app.domain.repositories.device_token_repository import DeviceTokenRepository
from app.domain.repositories.dose_log_repository import DoseLogRepository
from app.domain.repositories.medication_respository import MedicationRepository
from app.domain.services.reminder_schedule import dose_key, occurrences_between
from app.domain.value_objects.medication_enums import IntakeTiming

logger = logging.getLogger("uvicorn.error")

_TIMING_TEXT = {
    IntakeTiming.BEFORE_FOOD: "before food",
    IntakeTiming.AFTER_FOOD: "after food",
    IntakeTiming.WITH_FOOD: "with food",
    IntakeTiming.EMPTY_STOMACH: "on an empty stomach",
    IntakeTiming.BEFORE_SLEEP: "before sleep",
    IntakeTiming.ANYTIME: None,
}


def reminder_text(med: Medication, delayed: bool) -> tuple[str, str]:
    title = f"Did you take {med.name}?" if delayed else f"Time to take {med.name}"
    parts = [f"{med.dose} ({med.medicine_type.value})"]
    timing = _TIMING_TEXT.get(med.intake_timing)
    if timing:
        parts.append(timing)
    body = " - ".join(parts)
    if med.instructions:
        body += f". {med.instructions}"
    return title, body


class DispatchDueRemindersUseCase:
    """Send FCM pushes for doses that have just become due.

    Each dose is "claimed" by inserting a PENDING dose log; the unique
    constraint guarantees one push per dose even with several server
    instances, and doses already marked taken/skipped are never pushed.
    """

    def __init__(
        self,
        med_repo: MedicationRepository,
        dose_repo: DoseLogRepository,
        device_repo: DeviceTokenRepository,
        push: PushNotificationService,
        push_delay_minutes: int = 0,
        lookback_minutes: int = 15,
    ):
        self.med_repo = med_repo
        self.dose_repo = dose_repo
        self.device_repo = device_repo
        self.push = push
        self.delay = timedelta(minutes=push_delay_minutes)
        self.lookback = timedelta(minutes=lookback_minutes)

    async def execute(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        # A dose at time T is pushed at T + delay, as long as we're not more
        # than `lookback` late.
        window_end = now - self.delay + timedelta(seconds=1)
        window_start = window_end - self.lookback

        sent = 0
        for med in await self.med_repo.list_with_active_reminders():
            for when in occurrences_between(med.schedule, window_start, window_end):
                # Don't fire for a time that passed before the medicine was added.
                if med.created_at and when < med.created_at.replace(second=0, microsecond=0):
                    continue
                if not await self.dose_repo.claim_for_notification(med.user_id, med.id, when):
                    continue
                tokens = await self.device_repo.list_tokens(med.user_id)
                if not tokens:
                    continue
                key = dose_key(med.id, when)
                title, body = reminder_text(med, delayed=self.delay > timedelta(0))
                try:
                    invalid = await self.push.send(
                        tokens,
                        title,
                        body,
                        data={
                            "type": "medication_reminder",
                            "dose_key": key,
                            "medication_id": str(med.id),
                            "scheduled_for": when.isoformat(),
                        },
                        collapse_key=key,
                    )
                    await self.device_repo.remove_tokens(invalid)
                    sent += 1
                except Exception:
                    logger.exception("Failed to send reminder push for %s", key)
        return sent
