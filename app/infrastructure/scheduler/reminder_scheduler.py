import asyncio
import logging

from app.application.use_cases.reminder.dispatch_due_reminders import DispatchDueRemindersUseCase
from app.config import settings
from app.infrastructure.database.repositories.device_token_repository import (
    SQLAlchemyDeviceTokenRepository,
)
from app.infrastructure.database.repositories.dose_log_repository import SQLAlchemyDoseLogRepository
from app.infrastructure.database.repositories.medication_repository import (
    SQLAlchemyMedicationRepository,
)
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.notifications.push_notifier import FCMPushNotifier

logger = logging.getLogger("uvicorn.error")


async def run_once() -> int:
    async with AsyncSessionLocal() as session:
        use_case = DispatchDueRemindersUseCase(
            med_repo=SQLAlchemyMedicationRepository(session),
            dose_repo=SQLAlchemyDoseLogRepository(session),
            device_repo=SQLAlchemyDeviceTokenRepository(session),
            push=FCMPushNotifier(),
            push_delay_minutes=settings.REMINDER_PUSH_DELAY_MINUTES,
            lookback_minutes=settings.REMINDER_LOOKBACK_MINUTES,
        )
        return await use_case.execute()


async def reminder_loop() -> None:
    logger.info("Medication reminder scheduler started")
    while True:
        try:
            sent = await run_once()
            if sent:
                logger.info("Sent %d medication reminder push(es)", sent)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reminder scheduler tick failed")
        await asyncio.sleep(settings.REMINDER_CHECK_INTERVAL_SECONDS)
