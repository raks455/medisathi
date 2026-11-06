import asyncio
from sqlalchemy import text
from app.infrastructure.database.session import engine


async def main():
    async with engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL")
        )
        res = await conn.execute(text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name = 'hashed_password'"
        ))
        print("hashed_password is_nullable:", res.scalar())
    await engine.dispose()


asyncio.run(main())