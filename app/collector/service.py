"""Data collection service that orchestrates price fetching across all active trips."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.base import FlightDataSource, FlightPrice
from app.models import PriceSnapshot, TripRequest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = structlog.get_logger(__name__)


class CollectionService:
    """Orchestrates price collection across all active trip requests.

    Iterates each active trip, queries all registered flight data sources,
    persists price snapshots, and triggers the analyzer for recommendations.
    """

    def __init__(
        self,
        sources: list[FlightDataSource],
        session_factory: async_sessionmaker[AsyncSession],
        analyzer: object,
    ) -> None:
        """Initialize the collection service.

        Args:
            sources: List of FlightDataSource plugin instances to query.
            session_factory: Async session factory for database access.
            analyzer: PriceAnalyzer instance with an `analyze(trip, prices)` method.
        """
        self.sources = sources
        self.session_factory = session_factory
        self.analyzer = analyzer

    async def collect_all(self) -> None:
        """Run collection for all active trip requests.

        For each active trip:
        1. Collect prices from all configured sources
        2. Store price snapshots in the database
        3. Trigger the analyzer for recommendation generation

        Source failures are handled gracefully — a failing source is logged
        and skipped while collection continues with remaining sources.
        """
        async with self.session_factory() as session:
            trip_requests = await self._get_active_trips(session)

        logger.info("collection_started", active_trips=len(trip_requests))

        for trip in trip_requests:
            try:
                prices = await self._collect_for_trip(trip)
                await self._store_snapshots(trip.id, prices)
                await self.analyzer.analyze(trip, prices)
                logger.info(
                    "trip_collection_complete",
                    trip_id=trip.id,
                    origin=trip.origin,
                    destination=trip.destination,
                    prices_collected=len(prices),
                )
            except Exception as exc:
                logger.error(
                    "trip_collection_failed",
                    trip_id=trip.id,
                    error=str(exc),
                )

        logger.info("collection_finished", active_trips=len(trip_requests))

    async def _get_active_trips(self, session: AsyncSession) -> list[TripRequest]:
        """Fetch all active trip requests from the database."""
        result = await session.execute(
            select(TripRequest).where(TripRequest.is_active == True)  # noqa: E712
        )
        return list(result.scalars().all())

    async def _collect_for_trip(self, trip: TripRequest) -> list[FlightPrice]:
        """Collect prices from all sources for a trip's date range.

        Iterates each configured source and aggregates results.
        Individual source failures are logged and skipped.
        """
        all_prices: list[FlightPrice] = []

        for source in self.sources:
            try:
                prices = await source.search_flights(
                    origin=trip.origin,
                    destination=trip.destination,
                    departure_date=trip.earliest_departure,
                )
                all_prices.extend(prices)
                logger.debug(
                    "source_results",
                    source=source.__class__.__name__,
                    trip_id=trip.id,
                    results=len(prices),
                )
            except Exception as exc:
                logger.warning(
                    "source_failed",
                    source=source.__class__.__name__,
                    trip_id=trip.id,
                    error=str(exc),
                )

        return all_prices

    async def _store_snapshots(
        self, trip_request_id: int, prices: list[FlightPrice]
    ) -> None:
        """Persist collected prices as PriceSnapshot records."""
        if not prices:
            return

        async with self.session_factory() as session:
            for price in prices:
                snapshot = PriceSnapshot(
                    trip_request_id=trip_request_id,
                    airline_code=price.airline,
                    flight_number=price.flight_number,
                    departure_time=price.departure_time,
                    arrival_time=price.arrival_time,
                    fare_class=price.fare_class,
                    price_cents=price.price_cents,
                    flight_date=price.departure_date,
                    collected_at=datetime.utcnow(),
                )
                session.add(snapshot)
            await session.commit()

        logger.debug(
            "snapshots_stored",
            trip_request_id=trip_request_id,
            count=len(prices),
        )
