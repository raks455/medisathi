import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from app.application.interfaces.notification_service import PushNotificationService
from app.domain.entities.medication import Medication
from app.domain.repositories.device_token_repository import DeviceTokenRepository
from app.domain.repositories.dose_log_repository import DoseLogRepository
from app.domain.repositories.medication_respository import MedicationRepository
from app.domain.repositories.notification_repository import NotificationRepository
from app.domain.services.inventory_forecast import forecast_stock
from app.domain.services.reminder_schedule import dose_key, occurrences_between
from app.domain.value_objects.medication_enums import AlertStyle, IntakeTiming, NotificationType

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


def _amount(value: float) -> str:
    """30.0 -> '30', 2.5 -> '2.5'."""
    return f"{value:g}"


def refill_text(med: Medication, days_left: int, final: bool) -> tuple[str, str]:
    left = f"{_amount(med.inventory.quantity)} left"
    if final:
        return (
            f"{med.name} runs out today",
            f"{left}. Refill now so you do not miss a dose.",
        )
    when = "tomorrow" if days_left == 1 else f"in {days_left} days"
    return f"Refill {med.name} soon", f"{left} - it runs out {when}."


class _Notifier:
    """Saves a notification to the user's in-app list and pushes it to their phones."""

    def __init__(
        self,
        device_repo: DeviceTokenRepository,
        notification_repo: NotificationRepository,
        push: PushNotificationService,
    ):
        self.device_repo = device_repo
        self.notification_repo = notification_repo
        self.push = push

    async def notify(
        self,
        user_id: UUID,
        type: NotificationType,
        title: str,
        body: str,
        data: Dict[str, str],
        collapse_key: str,
        android_channel_id: Optional[str] = None,
    ) -> None:
        # The in-app list is written first so the user can still see the
        # reminder there when the push fails or no phone is registered.
        await self.notification_repo.add(user_id, type, title, body, data)
        tokens = await self.device_repo.list_tokens(user_id)
        if not tokens:
            return
        invalid = await self.push.send(
            tokens,
            title,
            body,
            data={"type": type.value, **data},
            collapse_key=collapse_key,
            android_channel_id=android_channel_id,
        )
        await self.device_repo.remove_tokens(invalid)


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
        notification_repo: NotificationRepository,
        push: PushNotificationService,
        push_delay_minutes: int = 0,
        lookback_minutes: int = 15,
        alarm_channel_id: Optional[str] = None,
    ):
        self.med_repo = med_repo
        self.dose_repo = dose_repo
        self.notifier = _Notifier(device_repo, notification_repo, push)
        self.delay = timedelta(minutes=push_delay_minutes)
        self.lookback = timedelta(minutes=lookback_minutes)
        self.alarm_channel_id = alarm_channel_id

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
                # ... or while the medicine is stopped.
                if med.was_paused_at(when):
                    continue
                if not await self.dose_repo.claim_for_notification(med.user_id, med.id, when):
                    continue
                key = dose_key(med.id, when)
                title, body = reminder_text(med, delayed=self.delay > timedelta(0))
                alarm = med.schedule.alert_style == AlertStyle.ALARM
                try:
                    await self.notifier.notify(
                        med.user_id,
                        NotificationType.MEDICATION_REMINDER,
                        title,
                        body,
                        data={
                            "dose_key": key,
                            "medication_id": str(med.id),
                            "scheduled_for": when.isoformat(),
                            "alert_style": med.schedule.alert_style.value,
                        },
                        collapse_key=key,
                        android_channel_id=self.alarm_channel_id if alarm else None,
                    )
                    sent += 1
                except Exception:
                    logger.exception("Failed to send reminder push for %s", key)
        return sent


class DispatchRefillRemindersUseCase:
    """Remind users to refill a medicine before (and on the day) it runs out.

    Two alerts per stock level: an "early" one `remind_days_before` days
    ahead, and a "final" one on the day the stock runs out. Each is claimed
    in the database first, so it is sent once. Updating the stock (a refill)
    clears the claim and starts over.
    """

    def __init__(
        self,
        med_repo: MedicationRepository,
        device_repo: DeviceTokenRepository,
        notification_repo: NotificationRepository,
        push: PushNotificationService,
        send_from_hour: int = 9,
    ):
        self.med_repo = med_repo
        self.notifier = _Notifier(device_repo, notification_repo, push)
        self.send_from_hour = send_from_hour

    async def execute(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        sent = 0
        for med in await self.med_repo.list_with_refill_reminders():
            inv = med.inventory
            if med.is_stopped or inv.alert_stage == "final":
                continue
            # Not in the middle of the user's night.
            if now.astimezone(ZoneInfo(med.schedule.timezone)).hour < self.send_from_hour:
                continue
            # Only the reminder window matters here, so look no further ahead.
            forecast = forecast_stock(med, now, horizon_days=inv.remind_days_before + 2)
            if forecast.days_left is None:
                continue

            if forecast.days_left <= 0:
                stage = "final"
            elif forecast.days_left <= inv.remind_days_before and inv.alert_stage is None:
                stage = "early"
            else:
                continue
            if not await self.med_repo.claim_refill_alert(med.id, stage):
                continue

            title, body = refill_text(med, forecast.days_left, final=stage == "final")
            try:
                await self.notifier.notify(
                    med.user_id,
                    NotificationType.REFILL_REMINDER,
                    title,
                    body,
                    data={
                        "medication_id": str(med.id),
                        "days_left": str(max(forecast.days_left, 0)),
                        "runs_out_on": forecast.runs_out_on.isoformat(),
                    },
                    collapse_key=f"refill:{med.id}",
                )
                sent += 1
            except Exception:
                logger.exception("Failed to send refill reminder for %s", med.id)
        return sent
