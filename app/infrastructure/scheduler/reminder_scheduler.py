import asyncio
import logging

from app.application.use_cases.reminder.dispatch_due_reminders import (
    DispatchDueRemindersUseCase, DispatchRefillRemindersUseCase,
)
from app.config import settings
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
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.notifications.push_notifier import FCMPushNotifier

logger = logging.getLogger("uvicorn.error")


async def run_once() -> int:
    """Send due dose reminders and refill reminders; returns how many were sent."""
    async with AsyncSessionLocal() as session:
        med_repo = SQLAlchemyMedicationRepository(session)
        device_repo = SQLAlchemyDeviceTokenRepository(session)
        notification_repo = SQLAlchemyNotificationRepository(session)
        push = FCMPushNotifier()

        doses = DispatchDueRemindersUseCase(
            med_repo=med_repo,
            dose_repo=SQLAlchemyDoseLogRepository(session),
            device_repo=device_repo,
            notification_repo=notification_repo,
            push=push,
            push_delay_minutes=settings.REMINDER_PUSH_DELAY_MINUTES,
            lookback_minutes=settings.REMINDER_LOOKBACK_MINUTES,
            alarm_channel_id=settings.ALARM_ANDROID_CHANNEL_ID,
        )
        refills = DispatchRefillRemindersUseCase(
            med_repo=med_repo,
            device_repo=device_repo,
            notification_repo=notification_repo,
            push=push,
            send_from_hour=settings.REFILL_REMINDER_HOUR,
        )
        return await doses.execute() + await refills.execute()


async def reminder_loop() -> None:
    logger.info("Medication reminder scheduler started")
    while True:
        try:
            sent = await run_once()
            if sent:
                logger.info("Sent %d medication / refill reminder(s)", sent)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reminder scheduler tick failed")
        await asyncio.sleep(settings.REMINDER_CHECK_INTERVAL_SECONDS)
