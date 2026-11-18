"""Small idempotent schema changes applied at startup.

`Base.metadata.create_all` creates missing tables but never adds a column to
a table that already exists, so columns added to existing tables are listed
here. Every statement must be safe to run on every start (IF NOT EXISTS).
Move these to Alembic revisions once the project starts using Alembic.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_STATEMENTS = [
    "ALTER TABLE medications ADD COLUMN IF NOT EXISTS paused_periods JSON",
    "ALTER TABLE medication_schedules ADD COLUMN IF NOT EXISTS alert_style "
    "VARCHAR(20) NOT NULL DEFAULT 'notification'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS language "
    "VARCHAR(5) NOT NULL DEFAULT 'en'",
    "ALTER TABLE medications ADD COLUMN IF NOT EXISTS photo_version VARCHAR(20)",
    "ALTER TABLE revoked_tokens ADD COLUMN IF NOT EXISTS rotated_at TIMESTAMPTZ",
]


async def run_startup_migrations(conn: AsyncConnection) -> None:
    for statement in _STATEMENTS:
        await conn.execute(text(statement))
