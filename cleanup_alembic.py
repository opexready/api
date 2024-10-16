from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import engine

async def clear_alembic_version():
    async with AsyncSession(engine) as session:
        await session.execute(text("DELETE FROM alembic_version"))
        await session.commit()

import asyncio
asyncio.run(clear_alembic_version())
