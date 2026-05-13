"""Strawberry GraphQL schema and resolvers for the Flight Deal Tracker."""

from datetime import date, datetime
from typing import Optional

import strawberry
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from strawberry.fastapi import GraphQLRouter

from app.database import get_session
from app.models import AnalysisResult, PriceSnapshot, TripRequest
from app.trip_manager.service import TripInput, TripService, TripValidationError


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
    stops: int
    total_duration_minutes: int
    segments: list[FlightSegmentType]


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
    is_active: bool
    created_at: datetime
    updated_at: datetime
    price_history: list[PriceSnapshotType]
    latest_analysis: Optional[AnalysisResultType]
    top_flight_options: list[FlightOptionType]


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


# --- Helper functions ---


def _map_trip_to_type(trip: TripRequest) -> TripRequestType:
    """Convert a SQLAlchemy TripRequest model to the GraphQL TripRequestType."""
    # Map price history
    price_history = [
        PriceSnapshotType(
            airline_code=snap.airline_code,
            fare_class=snap.fare_class,
            price_cents=snap.price_cents,
            flight_date=snap.flight_date,
            collected_at=snap.collected_at,
        )
        for snap in trip.price_snapshots
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

    # Derive top flight options from the latest price snapshots
    top_flight_options = _derive_top_flight_options(trip.price_snapshots, trip.latest_departure_time)

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
        is_active=trip.is_active,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
        price_history=price_history,
        latest_analysis=latest_analysis,
        top_flight_options=top_flight_options,
    )


def _derive_top_flight_options(snapshots: list[PriceSnapshot], latest_arrival_time: str | None = None) -> list[FlightOptionType]:
    """Derive top flight options from the latest price snapshots.

    Takes the most recently collected snapshots and returns up to 10
    cheapest options as flight options, filtered by arrival time constraint.
    """
    if not snapshots:
        return []

    # Find the latest collection timestamp
    latest_collected_at = max(snap.collected_at for snap in snapshots)

    # Use a 5-minute window to capture the entire batch
    from datetime import timedelta
    cutoff_time = latest_collected_at - timedelta(minutes=5)

    # Filter to only the most recent batch of snapshots
    latest_snapshots = [
        snap for snap in snapshots if snap.collected_at >= cutoff_time
    ]

    # Filter by arrival time constraint if set
    if latest_arrival_time:
        latest_snapshots = [
            snap for snap in latest_snapshots
            if not snap.arrival_time or _extract_time(snap.arrival_time) <= latest_arrival_time
        ]

    # Sort by price and take top 10
    sorted_snapshots = sorted(latest_snapshots, key=lambda s: s.price_cents)[:10]

    return [
        FlightOptionType(
            airline=snap.airline_code,
            flight_number=snap.flight_number,
            departure_time=snap.departure_time,
            arrival_time=snap.arrival_time,
            fare_class=snap.fare_class,
            price_cents=snap.price_cents,
            stops=snap.stops or 0,
            total_duration_minutes=snap.total_duration_minutes or 0,
            segments=_parse_segments_json(snap.segments_json),
        )
        for snap in sorted_snapshots
    ]


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
                .options(
                    selectinload(TripRequest.price_snapshots),
                    selectinload(TripRequest.analysis_results),
                )
            )
            trips = result.scalars().all()
            return [_map_trip_to_type(trip) for trip in trips]
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
                )
            )
            trip = result.scalar_one_or_none()
            if trip is None:
                return None
            return _map_trip_to_type(trip)
        return None


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
                    )
                )
            except TripValidationError as e:
                raise ValueError(e.message) from e

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
                    ),
                )
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
    async def trigger_collection(self) -> bool:
        """Manually trigger a price collection cycle. Awaits completion."""
        from app.main import _run_collection

        await _run_collection()
        return True


# --- Schema and Router ---

schema = strawberry.Schema(query=Query, mutation=Mutation)

graphql_router = GraphQLRouter(schema)
