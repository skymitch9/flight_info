from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


settings = Settings()

# pool_pre_ping transparently replaces connections dropped by DB restarts
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection helper that yields an async database session."""
    async with async_session_factory() as session:
        yield session


# Idempotent DDL run on startup for databases that predate newer model
# definitions (create_all only creates missing tables, never alters existing
# ones). Keep names in sync with the declarations in app/models.py.
_STARTUP_INDEX_DDL = [
    "ALTER TABLE trip_requests ADD COLUMN IF NOT EXISTS target_price_cents INTEGER",
    "ALTER TABLE trip_requests ADD COLUMN IF NOT EXISTS max_stops INTEGER",
    "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS min_price_cents INTEGER",
    "CREATE INDEX IF NOT EXISTS ix_price_snapshots_route_collected ON price_snapshots (route_id, collected_at)",
    "CREATE INDEX IF NOT EXISTS ix_price_snapshots_trip_request_id ON price_snapshots (trip_request_id)",
    "CREATE INDEX IF NOT EXISTS ix_price_snapshots_flight_date ON price_snapshots (flight_date)",
    "CREATE INDEX IF NOT EXISTS ix_analysis_results_trip_analyzed ON analysis_results (trip_request_id, analyzed_at)",
    "CREATE INDEX IF NOT EXISTS ix_notifications_trip_sent ON notifications (trip_request_id, sent_at)",
]


async def create_tables() -> None:
    """Create all database tables from ORM metadata.

    Uses run_sync to execute the synchronous create_all within
    the async engine's connection context. Also ensures hot-path
    indexes exist on databases created before they were declared.
    """
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for ddl in _STARTUP_INDEX_DDL:
            await conn.execute(text(ddl))
