from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FIREBASE_SERVICE_ACCOUNT_B64: str | None = None
    FIREBASE_SERVICE_ACCOUNT_FILE: str | None = None   # local: path to the key file
    FIREBASE_SERVICE_ACCOUNT_JSON: str | None = None   # Render: the whole JSON as an env var

    # Medication reminders
    REMINDER_SCHEDULER_ENABLED: bool = True      # run the push-reminder loop in this process
    REMINDER_CHECK_INTERVAL_SECONDS: int = 60
    REMINDER_LOOKBACK_MINUTES: int = 15          # still send a push this late (e.g. after a restart)
    REMINDER_PUSH_DELAY_MINUTES: int = 0         # >0 turns the push into a "you haven't taken it yet" nudge
    # "_v2" also vibrates in a long pattern and blinks the light (for users who
    # cannot hear the sound). Phones with an app from before it existed fall
    # back to their default channel.
    REMINDER_ANDROID_CHANNEL_ID: str = "medication_reminders_v2"
    ALARM_ANDROID_CHANNEL_ID: str = "medication_alarms"     # doses with alert_style "alarm"
    REFILL_REMINDER_HOUR: int = 9                # local hour from which refill reminders are sent
    DOSE_MISSED_AFTER_MINUTES: int = 60          # an unanswered dose counts as missed after this

    # Address phones reach this server at; used in links inside pushes
    # (medicine photos).
    PUBLIC_BASE_URL: str = "https://medisathi-c41p.onrender.com"
    MEDICINE_PHOTO_MAX_MB: int = 3

    # Health records (files are stored in Postgres)
    HEALTH_RECORD_MAX_FILE_MB: int = 10
    HEALTH_RECORD_QUOTA_MB: int = 200            # per user, all folders together

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()