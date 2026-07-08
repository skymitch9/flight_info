"""Trip Manager service for Trip_Request CRUD operations."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Route, TripRequest
from app.route_tracker.service import RouteTracker


class TripValidationError(Exception):
    """Raised when trip input fails validation."""

    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(message)


class TripNotFoundError(Exception):
    """Raised when a requested trip does not exist."""

    def __init__(self, trip_id: int):
        self.trip_id = trip_id
        super().__init__(f"Trip request with id {trip_id} not found")


@dataclass
class TripInput:
    """Input data for creating or updating a trip request."""

    origin: str
    destination: str
    earliest_departure: date
    latest_departure: date
    earliest_return: Optional[date] = None
    latest_return: Optional[date] = None
    latest_departure_time: Optional[str] = None  # "HH:MM"
    latest_return_time: Optional[str] = None  # "HH:MM"
    passenger_count: int = 1
    carry_on_bags: int = 1
    checked_bags: int = 0
    target_price_cents: Optional[int] = None


_IATA_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")


class TripService:
    """Business logic for trip request management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_trip(self, input: TripInput) -> TripRequest:
        """Validate and create a new trip request.

        Also links the trip to a Route via RouteTracker. If the route was
        dormant, it is reactivated so collection resumes. Round trips also
        ensure the reverse route exists so return-leg prices get collected.
        """
        self._validate(input)

        route = await self._ensure_routes(input)

        trip = TripRequest(
            origin=input.origin,
            destination=input.destination,
            earliest_departure=input.earliest_departure,
            latest_departure=input.latest_departure,
            earliest_return=input.earliest_return,
            latest_return=input.latest_return,
            latest_departure_time=input.latest_departure_time,
            latest_return_time=input.latest_return_time,
            passenger_count=input.passenger_count,
            carry_on_bags=input.carry_on_bags,
            checked_bags=input.checked_bags,
            target_price_cents=input.target_price_cents,
            is_active=True,
            route_id=route.id,
        )
        self.session.add(trip)
        await self.session.commit()
        await self.session.refresh(trip)
        return trip

    async def list_active_trips(self) -> list[TripRequest]:
        """Return all active trip requests."""
        result = await self.session.execute(
            select(TripRequest).where(TripRequest.is_active == True)  # noqa: E712
        )
        return list(result.scalars().all())

    async def list_fulfilled_trips(self) -> list[TripRequest]:
        """Return all completed trip contracts (fulfilled or expired).

        Eagerly loads price_snapshots and analysis_results for the history view.
        """
        result = await self.session.execute(
            select(TripRequest)
            .where(TripRequest.status.in_(["fulfilled", "expired"]))
            .options(
                selectinload(TripRequest.price_snapshots),
                selectinload(TripRequest.analysis_results),
            )
        )
        return list(result.scalars().all())

    async def get_trip(self, trip_id: int) -> TripRequest:
        """Fetch a single trip by ID. Raises TripNotFoundError if not found."""
        result = await self.session.execute(
            select(TripRequest).where(TripRequest.id == trip_id)
        )
        trip = result.scalar_one_or_none()
        if not trip:
            raise TripNotFoundError(trip_id)
        return trip

    async def fulfill_trip(self, trip_id: int) -> TripRequest:
        """Mark a trip as fulfilled (purchased).

        Sets status to "fulfilled" and records the fulfillment timestamp.
        Raises TripNotFoundError if the trip does not exist.
        Raises TripValidationError if the trip is already fulfilled.
        """
        trip = await self.get_trip(trip_id)

        if trip.status != "active":
            raise TripValidationError("Contract already fulfilled")

        trip.status = "fulfilled"
        trip.fulfilled_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(trip)
        return trip

    async def update_trip(self, trip_id: int, input: TripInput) -> TripRequest:
        """Validate and update an existing trip request.

        Re-links the trip to the correct route in case origin/destination
        changed, and ensures the reverse route exists for round trips.
        """
        self._validate(input)
        trip = await self.get_trip(trip_id)
        route = await self._ensure_routes(input)
        trip.route_id = route.id
        trip.origin = input.origin
        trip.destination = input.destination
        trip.earliest_departure = input.earliest_departure
        trip.latest_departure = input.latest_departure
        trip.earliest_return = input.earliest_return
        trip.latest_return = input.latest_return
        trip.latest_departure_time = input.latest_departure_time
        trip.latest_return_time = input.latest_return_time
        trip.passenger_count = input.passenger_count
        trip.carry_on_bags = input.carry_on_bags
        trip.checked_bags = input.checked_bags
        trip.target_price_cents = input.target_price_cents
        await self.session.commit()
        await self.session.refresh(trip)
        return trip

    async def delete_trip(self, trip_id: int) -> bool:
        """Soft-delete a trip request (set is_active=False)."""
        trip = await self.get_trip(trip_id)
        trip.is_active = False
        await self.session.commit()
        return True

    async def _ensure_routes(self, input: TripInput) -> Route:
        """Ensure routes exist for the trip, reactivating dormant ones.

        Creates/reactivates the outbound route (origin→destination) and, for
        round trips, the reverse route (destination→origin) so the collector
        also gathers return-leg prices. Returns the outbound route.
        """
        route_tracker = RouteTracker(self.session)

        route = await route_tracker.get_or_create_route(input.origin, input.destination)
        if route.status == "dormant":
            await route_tracker.reactivate_route(route.id)

        if input.earliest_return is not None:
            reverse = await route_tracker.get_or_create_route(
                input.destination, input.origin
            )
            if reverse.status == "dormant":
                await route_tracker.reactivate_route(reverse.id)

        return route

    def _validate(self, input: TripInput) -> None:
        """Enforce business rules on trip input.

        Validates:
        - origin and destination are valid 3-letter uppercase IATA codes
        - earliest_departure is in the future
        - latest_departure >= earliest_departure
        - If round-trip dates provided:
          - earliest_return >= earliest_departure
          - latest_return >= earliest_return
        """
        # Required fields
        if not input.origin:
            raise TripValidationError("Origin is required", field="origin")
        if not input.destination:
            raise TripValidationError("Destination is required", field="destination")
        if not input.earliest_departure:
            raise TripValidationError(
                "Earliest departure date is required", field="earliest_departure"
            )
        if not input.latest_departure:
            raise TripValidationError(
                "Latest departure date is required", field="latest_departure"
            )

        # IATA code format: exactly 3 uppercase letters
        if not _IATA_CODE_PATTERN.match(input.origin):
            raise TripValidationError(
                f"Origin '{input.origin}' is not a valid IATA code. "
                "Must be exactly 3 uppercase letters (e.g., ATL, JFK, LAX).",
                field="origin",
            )
        if not _IATA_CODE_PATTERN.match(input.destination):
            raise TripValidationError(
                f"Destination '{input.destination}' is not a valid IATA code. "
                "Must be exactly 3 uppercase letters (e.g., ATL, JFK, LAX).",
                field="destination",
            )

        # Earliest departure must be in the future
        today = date.today()
        if input.earliest_departure <= today:
            raise TripValidationError(
                "Earliest departure date must be in the future",
                field="earliest_departure",
            )

        # Latest departure must be >= earliest departure
        if input.latest_departure < input.earliest_departure:
            raise TripValidationError(
                "Latest departure date must be on or after earliest departure date",
                field="latest_departure",
            )

        # Round-trip date validation (only if return dates are provided)
        if input.earliest_return is not None:
            if input.earliest_return < input.earliest_departure:
                raise TripValidationError(
                    "Earliest return date must be on or after earliest departure date",
                    field="earliest_return",
                )

        if input.latest_return is not None:
            if input.earliest_return is None:
                raise TripValidationError(
                    "Latest return date requires earliest return date to be set",
                    field="latest_return",
                )
            if input.latest_return < input.earliest_return:
                raise TripValidationError(
                    "Latest return date must be on or after earliest return date",
                    field="latest_return",
                )

        # Passenger count validation
        if not (1 <= input.passenger_count <= 9):
            raise TripValidationError(
                "Passenger count must be between 1 and 9",
                field="passenger_count",
            )

        # Carry-on bags validation
        if not (0 <= input.carry_on_bags <= 2):
            raise TripValidationError(
                "Carry-on bags must be between 0 and 2",
                field="carry_on_bags",
            )

        # Checked bags validation
        if not (0 <= input.checked_bags <= 5):
            raise TripValidationError(
                "Checked bags must be between 0 and 5",
                field="checked_bags",
            )

        # Target price validation (optional; per-ticket main cabin fare)
        if input.target_price_cents is not None and input.target_price_cents <= 0:
            raise TripValidationError(
                "Target price must be greater than zero",
                field="target_price_cents",
            )
