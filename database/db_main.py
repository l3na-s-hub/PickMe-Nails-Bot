from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import config
from database.models import Base

engine = create_async_engine(config.db_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Создаёт все таблицы в БД, если они ещё не существуют."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
