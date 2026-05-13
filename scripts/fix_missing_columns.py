"""Fix missing columns in price_snapshots table."""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def fix():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@db:5432/flight_tracker")
    factory = async_sessionmaker(engine, class_=AsyncSession)
    async with factory() as session:
        columns_to_add = [
            ("stops", "INTEGER DEFAULT 0"),
            ("total_duration_minutes", "INTEGER DEFAULT 0"),
            ("segments_json", "TEXT"),
        ]
        for col, dtype in columns_to_add:
            result = await session.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM information_schema.columns "
                    "  WHERE table_name = 'price_snapshots' AND column_name = :col"
                    ")"
                ),
                {"col": col},
            )
            exists = result.scalar()
            if not exists:
                await session.execute(
                    text(f"ALTER TABLE price_snapshots ADD COLUMN {col} {dtype}")
                )
                print(f"Added {col}")
            else:
                print(f"{col} already exists")
        await session.commit()
    await engine.dispose()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(fix())
