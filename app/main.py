import asyncio
import contextlib
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.infrastructure.database.session import engine, Base
from app.interfaces.api.v1.auth import router as auth_router
from app.interfaces.api.v1.dashboard import router as dashboard_router
from app.interfaces.api.v1.medications import router as medications_router
from app.interfaces.api.v1.reminders import router as reminders_router
from app.interfaces.api.v1.notifications import router as notifications_router
from app.interfaces.api.v1.health_records import router as health_records_router
from app.interfaces.api.v1.wellness import moods_router, vitals_router
from app.interfaces.api.v1.womens_health import cycles_router, pregnancy_router
from app.interfaces.api.v1.feedback import router as feedback_router
from app.interfaces.api.v1.users import router as profile_router
from app.infrastructure.scheduler.reminder_scheduler import reminder_loop
from app.config import settings
from app.infrastructure.database.models.revoked_token import RevokedTokenModel  # noqa
from app.infrastructure.database.models.user import UserModel  # noqa
from app.infrastructure.database.models.medication import (  # noqa
    MedicationModel, MedicationScheduleModel, MedicationInventoryModel, DoseLogModel,
)
from app.infrastructure.database.models.device_token import DeviceTokenModel  # noqa
from app.infrastructure.database.models.notification import NotificationModel  # noqa
from app.infrastructure.database.models import health as _health_models  # noqa: F401
from app.infrastructure.database.migrations import run_startup_migrations
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (for development only)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Columns added to tables that already existed (create_all skips those).
        await run_startup_migrations(conn)

    reminder_task = None
    if settings.REMINDER_SCHEDULER_ENABLED:
        reminder_task = asyncio.create_task(reminder_loop())
    yield
    if reminder_task:
        reminder_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reminder_task
    await engine.dispose()

app = FastAPI(
    title="Medisathi API",
    description="Medisathi Backend - Clean Architecture",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(medications_router, prefix="/api/v1")
app.include_router(reminders_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(health_records_router, prefix="/api/v1")
app.include_router(vitals_router, prefix="/api/v1")
app.include_router(moods_router, prefix="/api/v1")
app.include_router(cycles_router, prefix="/api/v1")
app.include_router(pregnancy_router, prefix="/api/v1")
app.include_router(feedback_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")
@app.get("/")
async def root():
    return {"message": "Medisathi API is running"}

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}