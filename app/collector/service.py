"""Data collection service that orchestrates price fetching across all active routes."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.base import FlightDataSource, FlightPrice
from app.models import ApiUsage, PriceSnapshot, Route, TripRequest
from app.route_tracker.service import RouteTracker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = structlog.get_logger(__name__)


def sample_dates(start: date, end: date, max_dates: int) -> list[date]:
    """Return up to max_dates evenly spaced dates from [start, end], inclusive.

    Always includes the endpoints when they fit; dates before today are dropped
    so expired portions of a travel window are never searched.
    """
    today = date.today()
    start = max(start, today)
    if end < start or max_dates < 1:
        return []

    window_days = (end - start).days
    if window_days + 1 <= max_dates:
        return [start + timedelta(days=i) for i in range(window_days + 1)]

    # Evenly spaced sample including both endpoints
    step = window_days / (max_dates - 1)
    dates = {start + timedelta(days=round(i * step)) for i in range(max_dates)}
    return sorted(dates)


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
        max_dates_per_trip: int = 3,
        max_search_dates_per_route: int = 6,
        booking_horizon_days: int = 330,
        budgets: dict[str, int] | None = None,
    ) -> None:
        """Initialize the collection service.

        Args:
            sources: FlightDataSource instances in reliability order — the
                first source that returns results for a date wins; later
                sources are fallbacks used on error, empty results, or when
                an earlier source has exhausted its monthly budget.
            session_factory: Async session factory for database access.
            analyzer: PriceAnalyzer instance with an `analyze(trip, prices)` method.
            max_dates_per_trip: Max sampled dates each trip contributes.
            max_search_dates_per_route: Cap on searched dates per route per cycle.
            booking_horizon_days: Dates further out than this are not searched —
                airlines don't publish fares that far ahead. Trips beyond the
                horizon are picked up automatically once they come in range.
            budgets: Monthly search budget per source class name
                (e.g. {"SerpAPIFlightSource": 250}). Missing or 0 = unlimited.
        """
        self.sources = sources
        self.session_factory = session_factory
        self.analyzer = analyzer
        self.max_dates_per_trip = max_dates_per_trip
        self.max_search_dates_per_route = max_search_dates_per_route
        self.booking_horizon_days = booking_horizon_days
        self.budgets = budgets or {}

    async def collect_all(self, max_days_out: int | None = None) -> None:
        """Run collection for all active routes.

        For each active route:
        1. Determine which departure dates to search from the travel windows
           of active contracts (outbound windows for this route, return
           windows of round trips flying the reverse direction)
        2. Collect prices from all configured sources for those dates
        3. Store price snapshots linked to the route
        4. Update route.last_collected_at
        5. Trigger the analyzer for each active contract on that route

        Route failures are handled gracefully — a failing route is logged
        and skipped while collection continues with remaining routes.

        Args:
            max_days_out: When set, only trips departing within this many
                days contribute search dates ("close-in" runs — prices move
                fast near departure, so those trips get extra collections).
        """
        async with self.session_factory() as session:
            route_tracker = RouteTracker(session)
            routes = await route_tracker.get_active_routes()

            result = await session.execute(
                select(TripRequest).where(
                    TripRequest.is_active == True,  # noqa: E712
                    TripRequest.status == "active",
                )
            )
            active_trips = list(result.scalars().all())

        if max_days_out is not None:
            active_trips = self.filter_close_in(active_trips, max_days_out)
            if not active_trips:
                logger.info("closein_collection_skipped", reason="no close-in trips")
                return

        logger.info(
            "collection_started",
            active_routes=len(routes),
            max_days_out=max_days_out,
        )

        for route in routes:
            try:
                search_dates = self._search_dates_for_route(route, active_trips)
                if not search_dates:
                    logger.info(
                        "route_skipped_no_dates",
                        route_id=route.id,
                        origin=route.origin,
                        destination=route.destination,
                    )
                    continue
                prices = await self._collect_for_route(route, search_dates)
                await self._store_snapshots(route.id, prices)
                await self._update_last_collected(route.id)
                await self._trigger_analysis_for_route(route.id, prices)
                logger.info(
                    "route_collection_complete",
                    route_id=route.id,
                    origin=route.origin,
                    destination=route.destination,
                    dates_searched=[d.isoformat() for d in search_dates],
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

    @staticmethod
    def filter_close_in(
        trips: list[TripRequest], max_days_out: int
    ) -> list[TripRequest]:
        """Return only trips whose departure window starts within max_days_out days."""
        cutoff = date.today() + timedelta(days=max_days_out)
        return [t for t in trips if t.earliest_departure <= cutoff]

    def _search_dates_for_route(
        self, route: Route, active_trips: list[TripRequest]
    ) -> list[date]:
        """Build the set of departure dates to search for a route.

        Combines:
        - Outbound windows of trips flying this route (origin→destination)
        - Return windows of round trips flying the reverse direction, since
          their return legs depart from this route's origin

        Each trip contributes up to max_dates_per_trip sampled dates; the
        union is capped at max_search_dates_per_route to bound API usage.
        Windows are clamped to the booking horizon — dates airlines haven't
        published fares for yet are not searched, so far-future trips sit
        prepared at zero API cost until they come in range.
        """
        horizon_end = date.today() + timedelta(days=self.booking_horizon_days)
        dates: set[date] = set()

        def window_dates(start: date, end: date) -> list[date]:
            if start > horizon_end:
                return []  # entire window beyond the booking horizon — not yet collectable
            return sample_dates(start, min(end, horizon_end), self.max_dates_per_trip)

        for trip in active_trips:
            # Outbound legs on this route
            if trip.origin == route.origin and trip.destination == route.destination:
                dates.update(
                    window_dates(trip.earliest_departure, trip.latest_departure)
                )
            # Return legs of round trips on the reverse route
            if (
                trip.origin == route.destination
                and trip.destination == route.origin
                and trip.earliest_return is not None
            ):
                dates.update(
                    window_dates(
                        trip.earliest_return,
                        trip.latest_return or trip.earliest_return,
                    )
                )

        return sorted(dates)[: self.max_search_dates_per_route]

    async def _collect_for_route(
        self, route: Route, search_dates: list[date]
    ) -> list[FlightPrice]:
        """Collect prices for a route across the given dates.

        Sources are tried in reliability order per date: the first source
        that returns results wins; on error, empty results, or an exhausted
        monthly budget the next source is tried.
        """
        all_prices: list[FlightPrice] = []

        for search_date in search_dates:
            for source in self.sources:
                source_name = source.__class__.__name__
                # Google Flights sources issue one billed request per travel
                # class per call; other sources cost one request per call.
                cost = len(getattr(source, "_travel_classes", None) or [1])

                if not await self._consume_budget(source_name, cost):
                    logger.warning(
                        "source_budget_exhausted",
                        source=source_name,
                        route_id=route.id,
                        date=search_date.isoformat(),
                    )
                    continue

                try:
                    prices = await source.search_flights(
                        origin=route.origin,
                        destination=route.destination,
                        departure_date=search_date,
                    )
                except Exception as exc:
                    logger.warning(
                        "source_failed",
                        source=source_name,
                        route_id=route.id,
                        date=search_date.isoformat(),
                        error=str(exc),
                    )
                    continue

                logger.debug(
                    "source_results",
                    source=source_name,
                    route_id=route.id,
                    date=search_date.isoformat(),
                    results=len(prices),
                )
                if prices:
                    all_prices.extend(prices)
                    break  # first source with results wins for this date

        return all_prices

    async def _consume_budget(self, source_name: str, cost: int = 1) -> bool:
        """Check and consume `cost` searches from a source's monthly budget.

        Returns True if the source may be used (and records the calls), or
        False if the source has exhausted its budget this calendar month.
        Sources without a configured budget (or budget 0) are unlimited but
        still tracked for visibility.
        """
        budget = self.budgets.get(source_name, 0)
        month = datetime.utcnow().strftime("%Y-%m")

        async with self.session_factory() as session:
            result = await session.execute(
                select(ApiUsage).where(
                    ApiUsage.source == source_name, ApiUsage.month == month
                )
            )
            usage = result.scalar_one_or_none()
            if usage is None:
                usage = ApiUsage(source=source_name, month=month, calls=0)
                session.add(usage)

            if budget > 0 and usage.calls + cost > budget:
                await session.commit()  # persist the row even when skipping
                return False

            usage.calls += cost
            await session.commit()
            return True

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
