from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FIREBASE_SERVICE_ACCOUNT_B64: str | None = None
    class Config:
        env_file = ".env"
        case_sensitive = True
    FIREBASE_SERVICE_ACCOUNT_FILE: str | None = None   # local: path to the key file
   # FIREBASE_SERVICE_ACCOUNT_JSON: str | None = None   # Render: the whole JSON as an env var

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()