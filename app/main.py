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
from app.infrastructure.scheduler.reminder_scheduler import reminder_loop
from app.config import settings
from app.infrastructure.database.models.revoked_token import RevokedTokenModel  # noqa
from app.infrastructure.database.models.user import UserModel  # noqa
from app.infrastructure.database.models.medication import MedicationModel, MedicationScheduleModel, DoseLogModel  # noqa
from app.infrastructure.database.models.device_token import DeviceTokenModel  # noqa
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (for development only)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
@app.get("/")
async def root():
    return {"message": "Medisathi API is running"}

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}