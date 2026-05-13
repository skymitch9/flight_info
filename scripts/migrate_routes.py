"""
Migration script: Migrate existing data to route-level structure.

This script:
1. Creates the `routes` table if it doesn't exist.
2. Adds route_id, status, fulfilled_at columns to trip_requests if missing.
3. Adds route_id column to price_snapshots if missing.
4. For each distinct (origin, destination) in trip_requests, creates a Route record.
5. Updates trip_requests.route_id based on matching origin/destination.
6. Updates price_snapshots.route_id from their trip_request's route.
7. Sets trip_requests.status based on is_active.
8. Handles orphaned snapshots (creates route from snapshot's trip_request data).
9. Makes PriceSnapshot.trip_request_id nullable.
10. Adds NOT NULL constraints on route_id columns after population.

Idempotent: safe to re-run multiple times.

Usage:
    python scripts/migrate_routes.py
"""

import asyncio
import os
import sys

# Add project root to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings


async def get_database_url() -> str:
    """Get database URL from settings/environment."""
    try:
        settings = Settings()
        return settings.database_url
    except Exception:
        # Fallback to environment variable directly
        url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/flight_tracker")
        return url


async def column_exists(session: AsyncSession, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    result = await session.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.columns "
            "  WHERE table_name = :table AND column_name = :column"
            ")"
        ),
        {"table": table, "column": column},
    )
    return result.scalar()


async def table_exists(session: AsyncSession, table: str) -> bool:
    """Check if a table exists."""
    result = await session.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables "
            "  WHERE table_name = :table"
            ")"
        ),
        {"table": table},
    )
    return result.scalar()


async def constraint_exists(session: AsyncSession, constraint_name: str) -> bool:
    """Check if a constraint exists."""
    result = await session.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.table_constraints "
            "  WHERE constraint_name = :name"
            ")"
        ),
        {"name": constraint_name},
    )
    return result.scalar()


async def column_is_nullable(session: AsyncSession, table: str, column: str) -> bool:
    """Check if a column is nullable."""
    result = await session.execute(
        text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    row = result.fetchone()
    if row is None:
        return True  # Column doesn't exist, treat as nullable
    return row[0] == "YES"


async def step_1_create_routes_table(session: AsyncSession) -> None:
    """Step 1: Create the routes table if it doesn't exist."""
    print("Step 1: Creating routes table...")

    if await table_exists(session, "routes"):
        print("  → routes table already exists, skipping.")
        return

    await session.execute(
        text(
            """
            CREATE TABLE routes (
                id SERIAL PRIMARY KEY,
                origin VARCHAR(3) NOT NULL,
                destination VARCHAR(3) NOT NULL,
                status VARCHAR(10) NOT NULL DEFAULT 'active',
                last_collected_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT uq_route_origin_dest UNIQUE (origin, destination)
            )
            """
        )
    )
    await session.commit()
    print("  → routes table created.")


async def step_2_add_columns_to_trip_requests(session: AsyncSession) -> None:
    """Step 2: Add route_id, status, fulfilled_at columns to trip_requests if missing."""
    print("Step 2: Adding columns to trip_requests...")

    if not await column_exists(session, "trip_requests", "route_id"):
        await session.execute(
            text("ALTER TABLE trip_requests ADD COLUMN route_id INTEGER REFERENCES routes(id)")
        )
        print("  → Added route_id column.")
    else:
        print("  → route_id column already exists.")

    if not await column_exists(session, "trip_requests", "status"):
        await session.execute(
            text("ALTER TABLE trip_requests ADD COLUMN status VARCHAR(10) NOT NULL DEFAULT 'active'")
        )
        print("  → Added status column.")
    else:
        print("  → status column already exists.")

    if not await column_exists(session, "trip_requests", "fulfilled_at"):
        await session.execute(
            text("ALTER TABLE trip_requests ADD COLUMN fulfilled_at TIMESTAMP")
        )
        print("  → Added fulfilled_at column.")
    else:
        print("  → fulfilled_at column already exists.")

    await session.commit()


async def step_3_add_route_id_to_price_snapshots(session: AsyncSession) -> None:
    """Step 3: Add route_id column to price_snapshots if missing."""
    print("Step 3: Adding route_id to price_snapshots...")

    if not await column_exists(session, "price_snapshots", "route_id"):
        await session.execute(
            text("ALTER TABLE price_snapshots ADD COLUMN route_id INTEGER REFERENCES routes(id)")
        )
        print("  → Added route_id column.")
    else:
        print("  → route_id column already exists.")

    await session.commit()


async def step_4_create_routes_from_trip_requests(session: AsyncSession) -> None:
    """Step 4: For each distinct (origin, destination) in trip_requests, create a Route."""
    print("Step 4: Creating Route records from distinct trip_request pairs...")

    result = await session.execute(
        text("SELECT DISTINCT origin, destination FROM trip_requests")
    )
    pairs = result.fetchall()

    inserted = 0
    for origin, destination in pairs:
        # Use INSERT ... ON CONFLICT to be idempotent
        await session.execute(
            text(
                """
                INSERT INTO routes (origin, destination, status, created_at)
                VALUES (:origin, :destination, 'active', NOW())
                ON CONFLICT ON CONSTRAINT uq_route_origin_dest DO NOTHING
                """
            ),
            {"origin": origin, "destination": destination},
        )
        inserted += 1

    await session.commit()
    print(f"  → Processed {inserted} distinct (origin, destination) pairs.")


async def step_5_update_trip_requests_route_id(session: AsyncSession) -> None:
    """Step 5: Update trip_requests.route_id based on matching origin/destination."""
    print("Step 5: Updating trip_requests.route_id...")

    result = await session.execute(
        text(
            """
            UPDATE trip_requests tr
            SET route_id = r.id
            FROM routes r
            WHERE tr.origin = r.origin
              AND tr.destination = r.destination
              AND tr.route_id IS NULL
            """
        )
    )
    await session.commit()
    print(f"  → Updated {result.rowcount} trip_requests with route_id.")


async def step_6_update_price_snapshots_route_id(session: AsyncSession) -> None:
    """Step 6: Update price_snapshots.route_id from their trip_request's route."""
    print("Step 6: Updating price_snapshots.route_id from trip_requests...")

    result = await session.execute(
        text(
            """
            UPDATE price_snapshots ps
            SET route_id = tr.route_id
            FROM trip_requests tr
            WHERE ps.trip_request_id = tr.id
              AND ps.route_id IS NULL
              AND tr.route_id IS NOT NULL
            """
        )
    )
    await session.commit()
    print(f"  → Updated {result.rowcount} price_snapshots with route_id.")


async def step_7_set_trip_request_status(session: AsyncSession) -> None:
    """Step 7: Set trip_requests.status based on is_active."""
    print("Step 7: Setting trip_requests.status from is_active...")

    # Set status = 'active' where is_active = True and status is still default
    result_active = await session.execute(
        text(
            """
            UPDATE trip_requests
            SET status = 'active'
            WHERE is_active = TRUE AND status = 'active'
            """
        )
    )

    # Set status = 'fulfilled' where is_active = False
    result_fulfilled = await session.execute(
        text(
            """
            UPDATE trip_requests
            SET status = 'fulfilled',
                fulfilled_at = COALESCE(fulfilled_at, updated_at, created_at)
            WHERE is_active = FALSE AND status != 'fulfilled'
            """
        )
    )

    await session.commit()
    print(f"  → Set {result_active.rowcount} trip_requests to 'active'.")
    print(f"  → Set {result_fulfilled.rowcount} trip_requests to 'fulfilled'.")


async def step_8_handle_orphaned_snapshots(session: AsyncSession) -> None:
    """Step 8: Handle orphaned snapshots with no matching route."""
    print("Step 8: Handling orphaned price_snapshots...")

    # Find snapshots that still have no route_id
    # These could be snapshots whose trip_request has no route_id (shouldn't happen after step 5)
    # or snapshots with a trip_request_id that doesn't exist
    result = await session.execute(
        text(
            """
            SELECT DISTINCT ps.id, ps.trip_request_id
            FROM price_snapshots ps
            WHERE ps.route_id IS NULL
            """
        )
    )
    orphaned = result.fetchall()

    if not orphaned:
        print("  → No orphaned snapshots found.")
        return

    print(f"  → Found {len(orphaned)} orphaned snapshots. Resolving...")

    # For orphaned snapshots that have a trip_request_id, get the origin/dest from the trip_request
    # For those without a trip_request_id, we can't determine the route — skip them
    result = await session.execute(
        text(
            """
            SELECT DISTINCT tr.origin, tr.destination
            FROM price_snapshots ps
            JOIN trip_requests tr ON ps.trip_request_id = tr.id
            WHERE ps.route_id IS NULL AND tr.route_id IS NULL
            """
        )
    )
    missing_route_pairs = result.fetchall()

    # Create routes for any pairs that don't have one yet
    for origin, destination in missing_route_pairs:
        await session.execute(
            text(
                """
                INSERT INTO routes (origin, destination, status, created_at)
                VALUES (:origin, :destination, 'active', NOW())
                ON CONFLICT ON CONSTRAINT uq_route_origin_dest DO NOTHING
                """
            ),
            {"origin": origin, "destination": destination},
        )

    await session.commit()

    # Now update trip_requests that still have no route_id
    await session.execute(
        text(
            """
            UPDATE trip_requests tr
            SET route_id = r.id
            FROM routes r
            WHERE tr.origin = r.origin
              AND tr.destination = r.destination
              AND tr.route_id IS NULL
            """
        )
    )
    await session.commit()

    # Update orphaned snapshots that have a trip_request_id
    result = await session.execute(
        text(
            """
            UPDATE price_snapshots ps
            SET route_id = tr.route_id
            FROM trip_requests tr
            WHERE ps.trip_request_id = tr.id
              AND ps.route_id IS NULL
              AND tr.route_id IS NOT NULL
            """
        )
    )
    await session.commit()
    print(f"  → Resolved {result.rowcount} orphaned snapshots via trip_request.")

    # Check for any remaining orphaned snapshots (no trip_request_id at all)
    result = await session.execute(
        text("SELECT COUNT(*) FROM price_snapshots WHERE route_id IS NULL")
    )
    remaining = result.scalar()
    if remaining > 0:
        print(f"  ⚠ {remaining} snapshots still have no route_id (no trip_request_id to derive from).")
        print("    These snapshots cannot be automatically migrated.")


async def step_9_make_trip_request_id_nullable(session: AsyncSession) -> None:
    """Step 9: Make PriceSnapshot.trip_request_id nullable."""
    print("Step 9: Making price_snapshots.trip_request_id nullable...")

    if await column_is_nullable(session, "price_snapshots", "trip_request_id"):
        print("  → trip_request_id is already nullable.")
        return

    await session.execute(
        text("ALTER TABLE price_snapshots ALTER COLUMN trip_request_id DROP NOT NULL")
    )
    await session.commit()
    print("  → Made trip_request_id nullable.")


async def step_10_add_not_null_constraints(session: AsyncSession) -> None:
    """Step 10: Add NOT NULL constraints on route_id columns after population."""
    print("Step 10: Adding NOT NULL constraints on route_id columns...")

    # Check if there are any NULL route_ids remaining in trip_requests
    result = await session.execute(
        text("SELECT COUNT(*) FROM trip_requests WHERE route_id IS NULL")
    )
    null_trip_routes = result.scalar()

    if null_trip_routes > 0:
        print(f"  ⚠ Cannot add NOT NULL to trip_requests.route_id: {null_trip_routes} rows still NULL.")
        print("    Skipping constraint — manual intervention needed.")
    else:
        # Check if already NOT NULL
        if not await column_is_nullable(session, "trip_requests", "route_id"):
            print("  → trip_requests.route_id is already NOT NULL.")
        else:
            await session.execute(
                text("ALTER TABLE trip_requests ALTER COLUMN route_id SET NOT NULL")
            )
            await session.commit()
            print("  → Added NOT NULL constraint to trip_requests.route_id.")

    # Check if there are any NULL route_ids remaining in price_snapshots
    result = await session.execute(
        text("SELECT COUNT(*) FROM price_snapshots WHERE route_id IS NULL")
    )
    null_snapshot_routes = result.scalar()

    if null_snapshot_routes > 0:
        print(f"  ⚠ Cannot add NOT NULL to price_snapshots.route_id: {null_snapshot_routes} rows still NULL.")
        print("    Skipping constraint — manual intervention needed.")
    else:
        if not await column_is_nullable(session, "price_snapshots", "route_id"):
            print("  → price_snapshots.route_id is already NOT NULL.")
        else:
            await session.execute(
                text("ALTER TABLE price_snapshots ALTER COLUMN route_id SET NOT NULL")
            )
            await session.commit()
            print("  → Added NOT NULL constraint to price_snapshots.route_id.")


async def run_migration() -> None:
    """Run the full migration."""
    print("=" * 60)
    print("Route Migration Script")
    print("=" * 60)
    print()

    database_url = await get_database_url()
    print(f"Connecting to database...")

    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        try:
            await step_1_create_routes_table(session)
            await step_2_add_columns_to_trip_requests(session)
            await step_3_add_route_id_to_price_snapshots(session)
            await step_4_create_routes_from_trip_requests(session)
            await step_5_update_trip_requests_route_id(session)
            await step_6_update_price_snapshots_route_id(session)
            await step_7_set_trip_request_status(session)
            await step_8_handle_orphaned_snapshots(session)
            await step_9_make_trip_request_id_nullable(session)
            await step_10_add_not_null_constraints(session)

            print()
            print("=" * 60)
            print("Migration completed successfully!")
            print("=" * 60)

        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())
