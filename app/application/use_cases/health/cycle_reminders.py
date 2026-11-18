"""Push "your period is coming" and fertile-window reminders."""
import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.application.interfaces.notification_service import PushNotificationService
from app.application.use_cases.reminder.dispatch_due_reminders import (
    LanguageLookup, _Notifier, _language,
)
from app.domain.repositories.device_token_repository import DeviceTokenRepository
from app.domain.repositories.health_repositories import CycleRepository
from app.domain.repositories.notification_repository import NotificationRepository
from app.domain.services import cycle_forecast
from app.domain.value_objects.medication_enums import NotificationType

logger = logging.getLogger(__name__)


class DispatchCycleRemindersUseCase:
    def __init__(
        self,
        cycle_repo: CycleRepository,
        device_repo: DeviceTokenRepository,
        notification_repo: NotificationRepository,
        push: PushNotificationService,
        send_from_hour: int = 9,
        language_of: Optional[LanguageLookup] = None,
    ):
        self.cycle_repo = cycle_repo
        self.notifier = _Notifier(device_repo, notification_repo, push)
        self.send_from_hour = send_from_hour
        self.language_of = language_of

    async def execute(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        sent = 0
        for settings in await self.cycle_repo.list_reminder_settings():
            try:
                local = now.astimezone(ZoneInfo(settings.timezone))
            except (ZoneInfoNotFoundError, ValueError):
                continue
            # Not in the middle of the user's night.
            if local.hour < self.send_from_hour:
                continue
            periods = await self.cycle_repo.list(settings.user_id)
            if not periods:
                continue
            today = local.date()
            forecast = cycle_forecast.forecast(
                [cycle_forecast.LoggedPeriod(p.start_date, p.end_date) for p in periods],
                today,
            )
            # An open period that started recently counts as "in progress".
            latest = periods[0]
            if latest.end_date is None and (today - latest.start_date).days < 10:
                continue
            reminder = cycle_forecast.due_reminder(
                forecast, today, settings.remind_days_before,
                settings.period_reminders, settings.fertile_reminders,
                lang=await _language(self.language_of, settings.user_id),
            )
            if reminder is None or reminder.key == settings.alert_key:
                continue
            if not await self.cycle_repo.claim_alert(settings.user_id, reminder.key):
                continue
            try:
                await self.notifier.notify(
                    settings.user_id,
                    NotificationType.PERIOD_REMINDER,
                    reminder.title,
                    reminder.body,
                    data={"kind": reminder.key.split(":")[0],
                          "next_period_start": forecast.next_period_start.isoformat()},
                    collapse_key=f"cycle:{settings.user_id}",
                )
                sent += 1
            except Exception:
                logger.exception("Failed to send cycle reminder to %s", settings.user_id)
        return sent
