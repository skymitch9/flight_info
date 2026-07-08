"""Strawberry GraphQL schema and resolvers for the Flight Deal Tracker."""

import itertools
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Optional

import strawberry
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload
from strawberry.fastapi import GraphQLRouter

from app.database import get_session
from app.models import AnalysisResult, PriceSnapshot, Route, TripRequest
from app.pricing.calculator import LuggageConfig, calculate_total_price
from app.trip_manager.service import TripInput, TripNotFoundError, TripService, TripValidationError


# --- Strawberry Types ---


@strawberry.type
class FlightSegmentType:
    """A single leg/segment of a flight."""

    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    duration_minutes: int


@strawberry.type
class FlightOptionType:
    """A specific flight option derived from the latest price snapshots."""

    airline: str
    flight_number: str
    departure_time: str
    arrival_time: str
    fare_class: str
    price_cents: int
    total_price_cents: int
    flight_date: date
    stops: int
    total_duration_minutes: int
    segments: list[FlightSegmentType]


@strawberry.type
class RoundTripOptionType:
    """A paired outbound + return flight combination."""

    outbound: FlightOptionType
    return_flight: FlightOptionType
    combined_price_cents: int
    total_combined_price_cents: int


@strawberry.type
class AnalysisResultType:
    """LLM-generated price analysis recommendation."""

    recommendation: str
    explanation: str
    analyzed_at: datetime


@strawberry.type
class PriceSnapshotType:
    """A single price data point collected for a trip."""

    airline_code: str
    fare_class: str
    price_cents: int
    flight_date: date
    collected_at: datetime


@strawberry.type
class RouteType:
    """A unique origin-destination route that owns price collection."""

    id: int
    origin: str
    destination: str
    status: str
    last_collected_at: Optional[datetime]
    price_history: list[PriceSnapshotType]
    active_contracts: list["TripRequestType"]


@strawberry.type
class TripRequestType:
    """A user-defined trip request with nested price history and analysis."""

    id: int
    origin: str
    destination: str
    earliest_departure: date
    latest_departure: date
    earliest_return: Optional[date]
    latest_return: Optional[date]
    latest_departure_time: Optional[str]
    latest_return_time: Optional[str]
    passenger_count: int
    carry_on_bags: int
    checked_bags: int
    target_price_cents: Optional[int]
    is_active: bool
    status: str
    fulfilled_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    # When the route's prices were last refreshed (null before first collection)
    last_collected_at: Optional[datetime]
    price_history: list[PriceSnapshotType]
    latest_analysis: Optional[AnalysisResultType]
    top_flight_options: list[FlightOptionType]
    round_trip_options: list[RoundTripOptionType]
    # Date when price collection will begin, or null if already collecting.
    # Airlines publish fares ~330 days out; trips further ahead are "prepared"
    # and picked up automatically once in range.
    collection_starts_on: Optional[date]


@strawberry.input
class TripRequestInput:
    """Input for creating or updating a trip request."""

    origin: str
    destination: str
    earliest_departure: date
    latest_departure: date
    earliest_return: Optional[date] = None
    latest_return: Optional[date] = None
    latest_departure_time: Optional[str] = None
    latest_return_time: Optional[str] = None
    passenger_count: Optional[int] = 1
    carry_on_bags: Optional[int] = 1
    checked_bags: Optional[int] = 0
    target_price_cents: Optional[int] = None


# --- Helper functions ---


@lru_cache(maxsize=1)
def _booking_horizon_days() -> int:
    """Booking horizon from settings, cached for the process lifetime."""
    from app.config import Settings

    return Settings().booking_horizon_days


def _collection_starts_on(trip: TripRequest) -> Optional[date]:
    """Date collection begins for a trip, or None if already in range.

    Collection starts when the trip's earliest departure comes within the
    booking horizon (airlines publish fares ~330 days ahead).
    """
    horizon = _booking_horizon_days()
    if trip.earliest_departure > date.today() + timedelta(days=horizon):
        return trip.earliest_departure - timedelta(days=horizon)
    return None


def _map_trip_to_type(trip: TripRequest, return_snapshots: list[PriceSnapshot] | None = None) -> TripRequestType:
    """Convert a SQLAlchemy TripRequest model to the GraphQL TripRequestType."""
    # Use route snapshots (all fare classes) if available, fall back to trip snapshots
    # Check if route relationship is already loaded to avoid lazy-load in async context
    from sqlalchemy import inspect as sa_inspect
    trip_state = sa_inspect(trip)
    route_loaded = 'route' not in trip_state.unloaded
    if route_loaded and trip.route is not None:
        route_state = sa_inspect(trip.route)
        snaps_loaded = 'price_snapshots' not in route_state.unloaded
        all_snapshots = trip.route.price_snapshots if snaps_loaded and trip.route.price_snapshots else trip.price_snapshots
    else:
        all_snapshots = trip.price_snapshots

    # Map price history
    price_history = [
        PriceSnapshotType(
            airline_code=snap.airline_code,
            fare_class=snap.fare_class,
            price_cents=snap.price_cents,
            flight_date=snap.flight_date,
            collected_at=snap.collected_at,
        )
        for snap in all_snapshots
    ]

    # Get latest analysis (most recent by analyzed_at)
    latest_analysis = None
    if trip.analysis_results:
        latest = max(trip.analysis_results, key=lambda a: a.analyzed_at)
        latest_analysis = AnalysisResultType(
            recommendation=latest.recommendation,
            explanation=latest.explanation,
            analyzed_at=latest.analyzed_at,
        )

    # Build luggage config from trip for price calculations
    luggage = LuggageConfig(
        carry_on_bags=trip.carry_on_bags,
        checked_bags=trip.checked_bags,
    )
    passenger_count = trip.passenger_count

    # Derive top flight options from the route's price snapshots (all fare
    # classes), restricted to this trip's departure window — the route may
    # carry snapshots for other trips' dates and reverse-leg collections.
    outbound_snapshots = [
        s
        for s in all_snapshots
        if trip.earliest_departure <= s.flight_date <= trip.latest_departure
    ]
    top_flight_options = _derive_top_flight_options(outbound_snapshots, trip.latest_departure_time, luggage, passenger_count)

    # Derive round-trip options when trip has return dates
    if trip.earliest_return is not None:
        round_trip_options = _derive_round_trip_options(all_snapshots, return_snapshots or [], trip, luggage, passenger_count)
    else:
        round_trip_options = []

    return TripRequestType(
        id=trip.id,
        origin=trip.origin,
        destination=trip.destination,
        earliest_departure=trip.earliest_departure,
        latest_departure=trip.latest_departure,
        earliest_return=trip.earliest_return,
        latest_return=trip.latest_return,
        latest_departure_time=trip.latest_departure_time,
        latest_return_time=trip.latest_return_time,
        passenger_count=trip.passenger_count,
        carry_on_bags=trip.carry_on_bags,
        checked_bags=trip.checked_bags,
        target_price_cents=trip.target_price_cents,
        is_active=trip.is_active,
        status=trip.status,
        fulfilled_at=trip.fulfilled_at,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
        last_collected_at=(
            trip.route.last_collected_at if route_loaded and trip.route else None
        ),
        price_history=price_history,
        latest_analysis=latest_analysis,
        top_flight_options=top_flight_options,
        round_trip_options=round_trip_options,
        collection_starts_on=_collection_starts_on(trip),
    )


def _map_route_to_type(route: Route) -> RouteType:
    """Convert a SQLAlchemy Route model to the GraphQL RouteType."""
    price_history = [
        PriceSnapshotType(
            airline_code=snap.airline_code,
            fare_class=snap.fare_class,
            price_cents=snap.price_cents,
            flight_date=snap.flight_date,
            collected_at=snap.collected_at,
        )
        for snap in route.price_snapshots
    ]

    active_contracts = [
        _map_trip_to_type(trip)
        for trip in route.trip_requests
        if trip.status == "active"
    ]

    return RouteType(
        id=route.id,
        origin=route.origin,
        destination=route.destination,
        status=route.status,
        last_collected_at=route.last_collected_at,
        price_history=price_history,
        active_contracts=active_contracts,
    )


def _get_latest_batch(snapshots: list[PriceSnapshot]) -> list[PriceSnapshot]:
    """Get the latest batch of price snapshots per fare class using a 5-minute window.

    For each fare class, finds the most recent collected_at timestamp and returns
    all snapshots within a 5-minute window of that timestamp. This ensures premium
    fares (collected once daily) are included alongside economy fares (collected
    multiple times daily).
    """
    if not snapshots:
        return []

    # Group by fare class
    by_fare_class: dict[str, list[PriceSnapshot]] = {}
    for snap in snapshots:
        by_fare_class.setdefault(snap.fare_class, []).append(snap)

    # For each fare class, get the latest batch
    result: list[PriceSnapshot] = []
    for fare_class, group in by_fare_class.items():
        latest_collected_at = max(s.collected_at for s in group)
        cutoff_time = latest_collected_at - timedelta(minutes=5)
        result.extend(s for s in group if s.collected_at >= cutoff_time)

    return result


def _derive_top_flight_options(
    snapshots: list[PriceSnapshot],
    latest_arrival_time: str | None = None,
    luggage: LuggageConfig | None = None,
    passenger_count: int = 1,
) -> list[FlightOptionType]:
    """Derive top flight options from the latest price snapshots.

    Takes the most recently collected snapshots and returns up to 10
    cheapest options as flight options, filtered by arrival time constraint.
    Computes total_price_cents using the PriceCalculator when luggage config is provided.
    """
    if not snapshots:
        return []

    # Filter to only the most recent batch of snapshots
    latest_snapshots = _get_latest_batch(snapshots)

    # Filter by arrival time constraint if set
    if latest_arrival_time:
        latest_snapshots = [
            snap for snap in latest_snapshots
            if not snap.arrival_time or _extract_time(snap.arrival_time) <= latest_arrival_time
        ]

    # Sort by price and take top 10 per fare class
    from itertools import groupby
    fare_grouped = {}
    for snap in sorted(latest_snapshots, key=lambda s: s.fare_class):
        fare_grouped.setdefault(snap.fare_class, []).append(snap)

    sorted_snapshots = []
    for fare_class, group in fare_grouped.items():
        sorted_snapshots.extend(sorted(group, key=lambda s: s.price_cents)[:10])

    # Default luggage config if not provided
    if luggage is None:
        luggage = LuggageConfig(carry_on_bags=1, checked_bags=0)

    return [
        FlightOptionType(
            airline=snap.airline_code,
            flight_number=snap.flight_number,
            departure_time=snap.departure_time,
            arrival_time=snap.arrival_time,
            fare_class=snap.fare_class,
            price_cents=snap.price_cents,
            total_price_cents=calculate_total_price(
                base_fare_cents=snap.price_cents,
                airline_code=snap.airline_code,
                luggage=luggage,
                passenger_count=passenger_count,
            ).total_price_cents,
            flight_date=snap.flight_date,
            stops=snap.stops or 0,
            total_duration_minutes=snap.total_duration_minutes or 0,
            segments=_parse_segments_json(snap.segments_json),
        )
        for snap in sorted_snapshots
    ]


def _derive_round_trip_options(
    outbound_snapshots: list[PriceSnapshot],
    return_snapshots: list[PriceSnapshot],
    trip: TripRequest,
    luggage: LuggageConfig | None = None,
    passenger_count: int = 1,
) -> list[RoundTripOptionType]:
    """Derive round-trip flight options by pairing outbound and return flights.

    Filters both sets of snapshots to the latest batch, applies date/time
    constraints from the trip, forms the cartesian product, filters invalid
    pairs, sorts by combined price, and returns the top 10.
    Computes total_price_cents and total_combined_price_cents using PriceCalculator.
    """
    if not outbound_snapshots or not return_snapshots:
        return []

    # Default luggage config if not provided
    if luggage is None:
        luggage = LuggageConfig(carry_on_bags=1, checked_bags=0)

    # Filter to latest batch for each direction
    outbound_batch = _get_latest_batch(outbound_snapshots)
    return_batch = _get_latest_batch(return_snapshots)

    # Filter outbound flights by date range and time constraint
    valid_outbound = [
        snap for snap in outbound_batch
        if trip.earliest_departure <= snap.flight_date <= trip.latest_departure
    ]
    if trip.latest_departure_time:
        valid_outbound = [
            snap for snap in valid_outbound
            if not snap.arrival_time or _extract_time(snap.arrival_time) <= trip.latest_departure_time
        ]

    # Filter return flights by date range and time constraint
    valid_return = [
        snap for snap in return_batch
        if trip.earliest_return <= snap.flight_date <= trip.latest_return
    ]
    if trip.latest_return_time:
        valid_return = [
            snap for snap in valid_return
            if not snap.arrival_time or _extract_time(snap.arrival_time) <= trip.latest_return_time
        ]

    # Form cartesian product and filter pairs where return date >= outbound date
    pairs = [
        (out, ret)
        for out, ret in itertools.product(valid_outbound, valid_return)
        if ret.flight_date >= out.flight_date
    ]

    # Sort by combined price ascending and take top 10
    pairs.sort(key=lambda p: p[0].price_cents + p[1].price_cents)
    top_pairs = pairs[:10]

    # Map to RoundTripOptionType objects
    result = []
    for out, ret in top_pairs:
        out_total = calculate_total_price(
            base_fare_cents=out.price_cents,
            airline_code=out.airline_code,
            luggage=luggage,
            passenger_count=passenger_count,
        ).total_price_cents
        ret_total = calculate_total_price(
            base_fare_cents=ret.price_cents,
            airline_code=ret.airline_code,
            luggage=luggage,
            passenger_count=passenger_count,
        ).total_price_cents

        result.append(
            RoundTripOptionType(
                outbound=FlightOptionType(
                    airline=out.airline_code,
                    flight_number=out.flight_number,
                    departure_time=out.departure_time,
                    arrival_time=out.arrival_time,
                    fare_class=out.fare_class,
                    price_cents=out.price_cents,
                    total_price_cents=out_total,
                    flight_date=out.flight_date,
                    stops=out.stops or 0,
                    total_duration_minutes=out.total_duration_minutes or 0,
                    segments=_parse_segments_json(out.segments_json),
                ),
                return_flight=FlightOptionType(
                    airline=ret.airline_code,
                    flight_number=ret.flight_number,
                    departure_time=ret.departure_time,
                    arrival_time=ret.arrival_time,
                    fare_class=ret.fare_class,
                    price_cents=ret.price_cents,
                    total_price_cents=ret_total,
                    flight_date=ret.flight_date,
                    stops=ret.stops or 0,
                    total_duration_minutes=ret.total_duration_minutes or 0,
                    segments=_parse_segments_json(ret.segments_json),
                ),
                combined_price_cents=out.price_cents + ret.price_cents,
                total_combined_price_cents=out_total + ret_total,
            )
        )

    return result


def _parse_segments_json(segments_json: str | None) -> list[FlightSegmentType]:
    """Parse stored segments JSON into GraphQL types."""
    if not segments_json:
        return []
    import json
    try:
        data = json.loads(segments_json)
        return [
            FlightSegmentType(
                airline=s.get("airline", ""),
                flight_number=s.get("flight_number", ""),
                origin=s.get("origin", ""),
                destination=s.get("destination", ""),
                departure_time=s.get("departure_time", ""),
                arrival_time=s.get("arrival_time", ""),
                duration_minutes=s.get("duration_minutes", 0),
            )
            for s in data
        ]
    except (json.JSONDecodeError, TypeError):
        return []


def _extract_time(time_str: str) -> str:
    """Extract HH:MM from various time formats (ISO datetime, 'YYYY-MM-DD HH:MM', HH:MM, etc.)."""
    if not time_str:
        return "23:59"
    # If it looks like "2026-05-13T08:30" or "2026-05-13 08:30"
    if "T" in time_str or (len(time_str) > 10 and " " in time_str):
        try:
            # Split on T or space
            separator = "T" if "T" in time_str else " "
            parts = time_str.split(separator)
            time_part = parts[1][:5]  # "HH:MM"
            return time_part
        except (IndexError, ValueError):
            pass
    # If it's already HH:MM or HH:MM:SS
    if ":" in time_str and len(time_str) >= 5:
        return time_str[:5]
    return "23:59"


# --- Query resolvers ---


@strawberry.type
class Query:
    @strawberry.field
    async def trips(self) -> list[TripRequestType]:
        """Fetch all active trip requests with nested price history and analysis."""
        async for session in get_session():
            result = await session.execute(
                select(TripRequest)
                .where(TripRequest.is_active == True)  # noqa: E712
                .where(TripRequest.status == "active")
                .options(
                    selectinload(TripRequest.price_snapshots),
                    selectinload(TripRequest.analysis_results),
                    selectinload(TripRequest.route).selectinload(Route.price_snapshots),
                )
            )
            trips = result.scalars().all()

            # Batch-query reverse routes for trips with return dates
            trips_with_returns = [t for t in trips if t.earliest_return is not None]
            reverse_route_pairs = set(
                (t.destination, t.origin) for t in trips_with_returns
            )

            # Build a mapping of (origin, destination) -> list[PriceSnapshot] for reverse routes
            reverse_snapshots_map: dict[tuple[str, str], list[PriceSnapshot]] = {}
            if reverse_route_pairs:
                conditions = [
                    and_(Route.origin == orig, Route.destination == dest)
                    for orig, dest in reverse_route_pairs
                ]
                reverse_result = await session.execute(
                    select(Route)
                    .where(or_(*conditions))
                    .options(selectinload(Route.price_snapshots))
                )
                reverse_routes = reverse_result.scalars().all()
                for route in reverse_routes:
                    reverse_snapshots_map[(route.origin, route.destination)] = route.price_snapshots

            # Map trips to types, passing return snapshots where applicable
            mapped_trips = []
            for trip in trips:
                if trip.earliest_return is not None:
                    return_snapshots = reverse_snapshots_map.get(
                        (trip.destination, trip.origin), []
                    )
                else:
                    return_snapshots = []
                mapped_trips.append(_map_trip_to_type(trip, return_snapshots))

            return mapped_trips
        return []

    @strawberry.field
    async def trip(self, trip_id: int) -> Optional[TripRequestType]:
        """Fetch a single trip with full price history, latest analysis, and top flight options."""
        async for session in get_session():
            result = await session.execute(
                select(TripRequest)
                .where(TripRequest.id == trip_id)
                .options(
                    selectinload(TripRequest.price_snapshots),
                    selectinload(TripRequest.analysis_results),
                    selectinload(TripRequest.route).selectinload(Route.price_snapshots),
                )
            )
            trip = result.scalar_one_or_none()
            if trip is None:
                return None

            # Look up reverse route for return snapshots
            return_snapshots: list[PriceSnapshot] = []
            if trip.earliest_return is not None:
                reverse_result = await session.execute(
                    select(Route)
                    .where(Route.origin == trip.destination)
                    .where(Route.destination == trip.origin)
                    .options(selectinload(Route.price_snapshots))
                )
                reverse_route = reverse_result.scalar_one_or_none()
                if reverse_route is not None:
                    return_snapshots = reverse_route.price_snapshots

            return _map_trip_to_type(trip, return_snapshots)
        return None

    @strawberry.field
    async def fulfilled_trips(self) -> list[TripRequestType]:
        """Fetch all fulfilled trip contracts with their historical data.

        Returns fulfilled contracts with origin, destination, date ranges,
        fulfillment date, and final recommendation.
        """
        async for session in get_session():
            service = TripService(session)
            trips = await service.list_fulfilled_trips()
            return [_map_trip_to_type(trip) for trip in trips]
        return []

    @strawberry.field
    async def route(self, route_id: int) -> Optional[RouteType]:
        """Fetch a single route with full price history and active contracts."""
        async for session in get_session():
            result = await session.execute(
                select(Route)
                .where(Route.id == route_id)
                .options(
                    selectinload(Route.price_snapshots),
                    selectinload(Route.trip_requests).selectinload(TripRequest.price_snapshots),
                    selectinload(Route.trip_requests).selectinload(TripRequest.analysis_results),
                )
            )
            route = result.scalar_one_or_none()
            if route is None:
                return None
            return _map_route_to_type(route)
        return None

    @strawberry.field
    async def routes(self) -> list[RouteType]:
        """Fetch all tracked routes with status and price history."""
        async for session in get_session():
            result = await session.execute(
                select(Route)
                .options(
                    selectinload(Route.price_snapshots),
                    selectinload(Route.trip_requests).selectinload(TripRequest.price_snapshots),
                    selectinload(Route.trip_requests).selectinload(TripRequest.analysis_results),
                )
            )
            routes = result.scalars().all()
            return [_map_route_to_type(route) for route in routes]
        return []


# --- Mutation resolvers ---


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_trip(self, input: TripRequestInput) -> TripRequestType:
        """Create a new trip request. Validates inputs via TripService."""
        async for session in get_session():
            service = TripService(session)
            try:
                trip = await service.create_trip(
                    TripInput(
                        origin=input.origin,
                        destination=input.destination,
                        earliest_departure=input.earliest_departure,
                        latest_departure=input.latest_departure,
                        earliest_return=input.earliest_return,
                        latest_return=input.latest_return,
                        latest_departure_time=input.latest_departure_time,
                        latest_return_time=input.latest_return_time,
                        passenger_count=input.passenger_count if input.passenger_count is not None else 1,
                        carry_on_bags=input.carry_on_bags if input.carry_on_bags is not None else 1,
                        checked_bags=input.checked_bags if input.checked_bags is not None else 0,
                        target_price_cents=input.target_price_cents,
                    )
                )
            except TripValidationError as e:
                raise ValueError(e.message) from e

            # Collect prices for the new trip right away instead of waiting
            # for the next scheduled interval
            from app.main import trigger_early_collection

            trigger_early_collection()

            # Reload with relationships for the response
            await session.refresh(trip)
            result = await session.execute(
                select(TripRequest)
                .where(TripRequest.id == trip.id)
                .options(
                    selectinload(TripRequest.price_snapshots),
                    selectinload(TripRequest.analysis_results),
                )
            )
            trip = result.scalar_one()
            return _map_trip_to_type(trip)
        raise RuntimeError("Failed to acquire database session")

    @strawberry.mutation
    async def update_trip(self, trip_id: int, input: TripRequestInput) -> TripRequestType:
        """Update an existing trip request. Validates inputs via TripService."""
        async for session in get_session():
            service = TripService(session)
            try:
                trip = await service.update_trip(
                    trip_id,
                    TripInput(
                        origin=input.origin,
                        destination=input.destination,
                        earliest_departure=input.earliest_departure,
                        latest_departure=input.latest_departure,
                        earliest_return=input.earliest_return,
                        latest_return=input.latest_return,
                        latest_departure_time=input.latest_departure_time,
                        latest_return_time=input.latest_return_time,
                        passenger_count=input.passenger_count if input.passenger_count is not None else 1,
                        carry_on_bags=input.carry_on_bags if input.carry_on_bags is not None else 1,
                        checked_bags=input.checked_bags if input.checked_bags is not None else 0,
                        target_price_cents=input.target_price_cents,
                    ),
                )
            except TripValidationError as e:
                raise ValueError(e.message) from e

            # The travel window or route may have changed — refresh prices soon
            from app.main import trigger_early_collection

            trigger_early_collection()

            # Reload with relationships for the response
            result = await session.execute(
                select(TripRequest)
                .where(TripRequest.id == trip.id)
                .options(
                    selectinload(TripRequest.price_snapshots),
                    selectinload(TripRequest.analysis_results),
                )
            )
            trip = result.scalar_one()
            return _map_trip_to_type(trip)
        raise RuntimeError("Failed to acquire database session")

    @strawberry.mutation
    async def delete_trip(self, trip_id: int) -> bool:
        """Soft-delete a trip request (set is_active=False)."""
        async for session in get_session():
            service = TripService(session)
            try:
                return await service.delete_trip(trip_id)
            except TripValidationError as e:
                raise ValueError(e.message) from e
        raise RuntimeError("Failed to acquire database session")

    @strawberry.mutation
    async def fulfill_trip(self, trip_id: int) -> TripRequestType:
        """Mark a trip contract as fulfilled (purchased).

        Sets the contract status to "fulfilled" and records the fulfillment timestamp.
        The contract moves to the history section and no longer appears in active contracts.
        """
        async for session in get_session():
            service = TripService(session)
            try:
                trip = await service.fulfill_trip(trip_id)
            except TripNotFoundError as e:
                raise ValueError(str(e)) from e
            except TripValidationError as e:
                raise ValueError(e.message) from e

            # Reload with relationships for the response
            result = await session.execute(
                select(TripRequest)
                .where(TripRequest.id == trip.id)
                .options(
                    selectinload(TripRequest.price_snapshots),
                    selectinload(TripRequest.analysis_results),
                )
            )
            trip = result.scalar_one()
            return _map_trip_to_type(trip)
        raise RuntimeError("Failed to acquire database session")

    @strawberry.mutation
    async def trigger_collection(self) -> bool:
        """Manually trigger a price collection cycle.

        Schedules a one-off collection run and returns immediately — a full
        cycle can take minutes, which would time out the HTTP request if
        awaited inline.
        """
        from app.main import trigger_early_collection

        trigger_early_collection()
        return True


# --- Schema and Router ---

schema = strawberry.Schema(query=Query, mutation=Mutation)

graphql_router = GraphQLRouter(schema)
