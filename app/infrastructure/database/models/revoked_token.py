from datetime import datetime
from uuid import UUID
from sqlalchemy import String, DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.infrastructure.database.session import Base

class RevokedTokenModel(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Set when a refresh token was exchanged for a new one (not on logout).
    # Added by run_startup_migrations() on existing databases.
    rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )