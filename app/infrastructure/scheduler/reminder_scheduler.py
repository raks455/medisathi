import asyncio
import logging
import time

from app.application.use_cases.reminder.dispatch_due_reminders import (
    DispatchDueRemindersUseCase, DispatchRefillRemindersUseCase,
)
from app.application.use_cases.health.cycle_reminders import DispatchCycleRemindersUseCase
from app.config import settings
from app.infrastructure.database.repositories.health_repositories import (
    SQLAlchemyCycleRepository,
)
from app.infrastructure.database.repositories.device_token_repository import (
    SQLAlchemyDeviceTokenRepository,
)
from app.infrastructure.database.repositories.dose_log_repository import SQLAlchemyDoseLogRepository
from app.infrastructure.database.repositories.medication_repository import (
    SQLAlchemyMedicationRepository,
)
from app.infrastructure.database.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
from app.infrastructure.database.repositories.user_repository import SQLAlchemyUserRepository
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.security.photo_links import medicine_photo_url
from app.infrastructure.notifications.push_notifier import FCMPushNotifier

logger = logging.getLogger("uvicorn.error")

# Period reminders are daily, so checking every few minutes is plenty.
_CYCLE_CHECK_SECONDS = 600
_last_cycle_check = 0.0


async def run_once() -> int:
    """Send due dose reminders and refill reminders; returns how many were sent."""
    async with AsyncSessionLocal() as session:
        med_repo = SQLAlchemyMedicationRepository(session)
        device_repo = SQLAlchemyDeviceTokenRepository(session)
        notification_repo = SQLAlchemyNotificationRepository(session)
        push = FCMPushNotifier()

        # Each user's language, looked up once per run.
        user_repo = SQLAlchemyUserRepository(session)
        languages: dict = {}

        async def language_of(user_id):
            if user_id not in languages:
                languages[user_id] = await user_repo.get_language(user_id)
            return languages[user_id]

        doses = DispatchDueRemindersUseCase(
            med_repo=med_repo,
            dose_repo=SQLAlchemyDoseLogRepository(session),
            device_repo=device_repo,
            notification_repo=notification_repo,
            push=push,
            push_delay_minutes=settings.REMINDER_PUSH_DELAY_MINUTES,
            lookback_minutes=settings.REMINDER_LOOKBACK_MINUTES,
            alarm_channel_id=settings.ALARM_ANDROID_CHANNEL_ID,
            language_of=language_of,
            photo_url_of=medicine_photo_url,
        )
        refills = DispatchRefillRemindersUseCase(
            med_repo=med_repo,
            device_repo=device_repo,
            notification_repo=notification_repo,
            push=push,
            send_from_hour=settings.REFILL_REMINDER_HOUR,
            language_of=language_of,
        )
        sent = await doses.execute() + await refills.execute()

        global _last_cycle_check
        if time.monotonic() - _last_cycle_check >= _CYCLE_CHECK_SECONDS:
            _last_cycle_check = time.monotonic()
            sent += await DispatchCycleRemindersUseCase(
                cycle_repo=SQLAlchemyCycleRepository(session),
                device_repo=device_repo,
                notification_repo=notification_repo,
                push=push,
                send_from_hour=settings.REFILL_REMINDER_HOUR,
                language_of=language_of,
            ).execute()
        return sent


async def reminder_loop() -> None:
    logger.info("Medication reminder scheduler started")
    while True:
        try:
            sent = await run_once()
            if sent:
                logger.info("Sent %d medication / refill / cycle reminder(s)", sent)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reminder scheduler tick failed")
        await asyncio.sleep(settings.REMINDER_CHECK_INTERVAL_SECONDS)
