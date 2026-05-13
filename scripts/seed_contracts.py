"""
Seed script: Create trip contracts for price tracking.

Creates the following contracts:
- PHX→ATL: Fixed dates September 3-10, morning departure / afternoon return (Arizona time)
- PHX→KIX: Flexible dates September-November 2026 (Osaka Kansai)
- PHX→NRT: Flexible dates September-November 2026 (Tokyo Narita)
- PHX→HND: Flexible dates September-November 2026 (Tokyo Haneda)

Uses TripService.create_trip() which automatically calls RouteTracker.get_or_create_route()
to ensure the Route record is created or reused for deduplication.

Usage:
    python scripts/seed_contracts.py
"""

import asyncio
import os
import sys
from datetime import date

# Add project root to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.trip_manager.service import TripInput, TripService


async def get_database_url() -> str:
    """Get database URL from settings/environment."""
    try:
        settings = Settings()
        return settings.database_url
    except Exception:
        url = os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@db:5432/flight_tracker",
        )
        return url


async def seed_phx_atl(session: AsyncSession) -> None:
    """Create PHX→ATL contract: September 3-10, fixed dates.

    - Departure: September 3, morning departure constraint (must depart by noon)
    - Return: September 10, afternoon arrival constraint (Arizona time, by 18:00)
    - Route record is created/reused via RouteTracker automatically
    """
    print("Creating PHX→ATL contract...")
    print("  Origin: PHX (Phoenix)")
    print("  Destination: ATL (Atlanta)")
    print("  Departure: 2026-09-03 (morning, depart by 12:00)")
    print("  Return: 2026-09-10 (afternoon arrival, by 18:00 Arizona time)")

    trip_input = TripInput(
        origin="PHX",
        destination="ATL",
        earliest_departure=date(2026, 9, 3),
        latest_departure=date(2026, 9, 3),
        earliest_return=date(2026, 9, 10),
        latest_return=date(2026, 9, 10),
        latest_departure_time="12:00",
        latest_return_time="18:00",
    )

    service = TripService(session)
    trip = await service.create_trip(trip_input)

    print(f"\n  ✓ Contract created (id={trip.id})")
    print(f"  ✓ Route linked (route_id={trip.route_id})")
    print(f"  ✓ Status: {trip.status}")


async def seed_phx_kix(session: AsyncSession) -> None:
    """Create PHX→KIX contract: flexible dates September-November 2026.

    - Osaka Kansai International Airport
    - Departure window: September 1 - November 30, 2026
    - Return window: September 15 - December 14, 2026 (at least 2 weeks trip)
    - No time constraints
    - Route record is created/reused via RouteTracker automatically
    """
    print("Creating PHX→KIX contract...")
    print("  Origin: PHX (Phoenix)")
    print("  Destination: KIX (Osaka Kansai)")
    print("  Departure window: 2027-09-01 to 2027-11-30")
    print("  Return window: 2027-09-15 to 2027-12-14")
    print("  Time constraints: None (flexible)")

    trip_input = TripInput(
        origin="PHX",
        destination="KIX",
        earliest_departure=date(2027, 9, 1),
        latest_departure=date(2027, 11, 30),
        earliest_return=date(2027, 9, 15),
        latest_return=date(2027, 12, 14),
        latest_departure_time=None,
        latest_return_time=None,
    )

    service = TripService(session)
    trip = await service.create_trip(trip_input)

    print(f"\n  ✓ Contract created (id={trip.id})")
    print(f"  ✓ Route linked (route_id={trip.route_id})")
    print(f"  ✓ Status: {trip.status}")


async def seed_phx_nrt(session: AsyncSession) -> None:
    """Create PHX→NRT contract: flexible dates September-November 2026.

    - Tokyo Narita International Airport
    - Departure window: September 1 - November 30, 2026
    - Return window: September 15 - December 14, 2026 (at least 2 weeks trip)
    - No time constraints
    - Route record is created/reused via RouteTracker automatically
    """
    print("Creating PHX→NRT contract...")
    print("  Origin: PHX (Phoenix)")
    print("  Destination: NRT (Tokyo Narita)")
    print("  Departure window: 2027-09-01 to 2027-11-30")
    print("  Return window: 2027-09-15 to 2027-12-14")
    print("  Time constraints: None (flexible)")

    trip_input = TripInput(
        origin="PHX",
        destination="NRT",
        earliest_departure=date(2027, 9, 1),
        latest_departure=date(2027, 11, 30),
        earliest_return=date(2027, 9, 15),
        latest_return=date(2027, 12, 14),
        latest_departure_time=None,
        latest_return_time=None,
    )

    service = TripService(session)
    trip = await service.create_trip(trip_input)

    print(f"\n  ✓ Contract created (id={trip.id})")
    print(f"  ✓ Route linked (route_id={trip.route_id})")
    print(f"  ✓ Status: {trip.status}")


async def seed_phx_hnd(session: AsyncSession) -> None:
    """Create PHX→HND contract: flexible dates September-November 2026.

    - Tokyo Haneda International Airport
    - Departure window: September 1 - November 30, 2026
    - Return window: September 15 - December 14, 2026 (at least 2 weeks trip)
    - No time constraints
    - Route record is created/reused via RouteTracker automatically
    """
    print("Creating PHX→HND contract...")
    print("  Origin: PHX (Phoenix)")
    print("  Destination: HND (Tokyo Haneda)")
    print("  Departure window: 2027-09-01 to 2027-11-30")
    print("  Return window: 2027-09-15 to 2027-12-14")
    print("  Time constraints: None (flexible)")

    trip_input = TripInput(
        origin="PHX",
        destination="HND",
        earliest_departure=date(2027, 9, 1),
        latest_departure=date(2027, 11, 30),
        earliest_return=date(2027, 9, 15),
        latest_return=date(2027, 12, 14),
        latest_departure_time=None,
        latest_return_time=None,
    )

    service = TripService(session)
    trip = await service.create_trip(trip_input)

    print(f"\n  ✓ Contract created (id={trip.id})")
    print(f"  ✓ Route linked (route_id={trip.route_id})")
    print(f"  ✓ Status: {trip.status}")


async def run_seed() -> None:
    """Run the seed script."""
    print("=" * 60)
    print("Contract Seed Script")
    print("=" * 60)
    print()

    database_url = await get_database_url()
    print("Connecting to database...")

    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        try:
            await seed_phx_atl(session)
            print()
            await seed_phx_kix(session)
            print()
            await seed_phx_nrt(session)
            print()
            await seed_phx_hnd(session)

            print()
            print("=" * 60)
            print("Seed completed successfully!")
            print("=" * 60)

        except Exception as e:
            print(f"\n✗ Seed failed: {e}")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_seed())
