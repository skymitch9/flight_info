"""Data collection service that orchestrates price fetching across all active routes."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.base import FlightDataSource, FlightPrice
from app.models import PriceSnapshot, Route, TripRequest
from app.route_tracker.service import RouteTracker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = structlog.get_logger(__name__)


class CollectionService:
    """Orchestrates price collection across all active routes.

    Iterates each active route, queries all registered flight data sources,
    persists price snapshots at the route level, and triggers the analyzer
    for each active contract on that route.
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
        """Run collection for all active routes.

        For each active route:
        1. Collect prices from all configured sources
        2. Store price snapshots linked to the route
        3. Update route.last_collected_at
        4. Trigger the analyzer for each active contract on that route

        Route failures are handled gracefully — a failing route is logged
        and skipped while collection continues with remaining routes.
        """
        async with self.session_factory() as session:
            route_tracker = RouteTracker(session)
            routes = await route_tracker.get_active_routes()

        logger.info("collection_started", active_routes=len(routes))

        for route in routes:
            try:
                prices = await self._collect_for_route(route)
                await self._store_snapshots(route.id, prices)
                await self._update_last_collected(route.id)
                await self._trigger_analysis_for_route(route.id, prices)
                logger.info(
                    "route_collection_complete",
                    route_id=route.id,
                    origin=route.origin,
                    destination=route.destination,
                    prices_collected=len(prices),
                )
            except Exception as exc:
                logger.error(
                    "route_collection_failed",
                    route_id=route.id,
                    origin=route.origin,
                    destination=route.destination,
                    error=str(exc),
                )

        logger.info("collection_finished", active_routes=len(routes))

    async def _collect_for_route(self, route: Route) -> list[FlightPrice]:
        """Collect prices from all sources for a route.

        Iterates each configured source and aggregates results.
        Individual source failures are logged and skipped.
        """
        all_prices: list[FlightPrice] = []

        for source in self.sources:
            try:
                prices = await source.search_flights(
                    origin=route.origin,
                    destination=route.destination,
                    departure_date=datetime.utcnow().date(),
                )
                all_prices.extend(prices)
                logger.debug(
                    "source_results",
                    source=source.__class__.__name__,
                    route_id=route.id,
                    results=len(prices),
                )
            except Exception as exc:
                logger.warning(
                    "source_failed",
                    source=source.__class__.__name__,
                    route_id=route.id,
                    error=str(exc),
                )

        return all_prices

    async def _store_snapshots(
        self, route_id: int, prices: list[FlightPrice]
    ) -> None:
        """Persist collected prices as PriceSnapshot records linked to a route."""
        import json

        if not prices:
            return

        async with self.session_factory() as session:
            for price in prices:
                # Serialize segments to JSON if present
                segments_json = None
                if price.segments:
                    segments_json = json.dumps([
                        {
                            "airline": s.airline,
                            "flight_number": s.flight_number,
                            "origin": s.origin,
                            "destination": s.destination,
                            "departure_time": s.departure_time,
                            "arrival_time": s.arrival_time,
                            "duration_minutes": s.duration_minutes,
                        }
                        for s in price.segments
                    ])

                snapshot = PriceSnapshot(
                    route_id=route_id,
                    trip_request_id=None,
                    airline_code=price.airline,
                    flight_number=price.flight_number,
                    departure_time=price.departure_time,
                    arrival_time=price.arrival_time,
                    fare_class=price.fare_class,
                    price_cents=price.price_cents,
                    flight_date=price.departure_date,
                    stops=price.stops,
                    total_duration_minutes=price.total_duration_minutes,
                    segments_json=segments_json,
                    collected_at=datetime.utcnow(),
                )
                session.add(snapshot)
            await session.commit()

        logger.debug(
            "snapshots_stored",
            route_id=route_id,
            count=len(prices),
        )

    async def _update_last_collected(self, route_id: int) -> None:
        """Update the route's last_collected_at timestamp after successful collection."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(Route).where(Route.id == route_id)
            )
            route = result.scalar_one_or_none()
            if route:
                route.last_collected_at = datetime.utcnow()
                await session.commit()

    async def _trigger_analysis_for_route(
        self, route_id: int, prices: list[FlightPrice]
    ) -> None:
        """Trigger analysis for each active contract on the given route.

        This makes collected price data available to all contracts referencing
        the route for analysis purposes.
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(TripRequest).where(
                    TripRequest.route_id == route_id,
                    TripRequest.status == "active",
                )
            )
            active_contracts = list(result.scalars().all())

        for contract in active_contracts:
            try:
                await self.analyzer.analyze(contract, prices)
                logger.debug(
                    "analysis_triggered",
                    route_id=route_id,
                    trip_id=contract.id,
                )
            except Exception as exc:
                logger.warning(
                    "analysis_failed",
                    route_id=route_id,
                    trip_id=contract.id,
                    error=str(exc),
                )


def _extract_arrival_time(time_str: str) -> str:
    """Extract HH:MM from arrival time string."""
    if not time_str:
        return "23:59"
    if "T" in time_str or (len(time_str) > 10 and " " in time_str):
        try:
            separator = "T" if "T" in time_str else " "
            parts = time_str.split(separator)
            return parts[1][:5]
        except (IndexError, ValueError):
            pass
    if ":" in time_str and len(time_str) >= 5:
        return time_str[:5]
    return "23:59"
