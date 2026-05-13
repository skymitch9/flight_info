from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


settings = Settings()

engine = create_async_engine(settings.database_url, echo=False)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection helper that yields an async database session."""
    async with async_session_factory() as session:
        yield session


async def create_tables() -> None:
    """Create all database tables from ORM metadata.

    Uses run_sync to execute the synchronous create_all within
    the async engine's connection context.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
