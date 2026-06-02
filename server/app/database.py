# Подключение к базе данных PostgreSQL
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=600,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    # DDL миграции больше не выполняем на старте приложения.
    # Предполагается, что перед запуском сервис обновлён через:
    #   alembic upgrade head
    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text("SELECT 1"))
