"""Trip Manager service for Trip_Request CRUD operations."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TripRequest


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


_IATA_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")


class TripService:
    """Business logic for trip request management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_trip(self, input: TripInput) -> TripRequest:
        """Validate and create a new trip request."""
        self._validate(input)
        trip = TripRequest(
            origin=input.origin,
            destination=input.destination,
            earliest_departure=input.earliest_departure,
            latest_departure=input.latest_departure,
            earliest_return=input.earliest_return,
            latest_return=input.latest_return,
            latest_departure_time=input.latest_departure_time,
            latest_return_time=input.latest_return_time,
            is_active=True,
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

    async def get_trip(self, trip_id: int) -> TripRequest:
        """Fetch a single trip by ID. Raises TripNotFoundError if not found."""
        result = await self.session.execute(
            select(TripRequest).where(TripRequest.id == trip_id)
        )
        trip = result.scalar_one_or_none()
        if not trip:
            raise TripNotFoundError(trip_id)
        return trip

    async def update_trip(self, trip_id: int, input: TripInput) -> TripRequest:
        """Validate and update an existing trip request."""
        self._validate(input)
        trip = await self.get_trip(trip_id)
        trip.origin = input.origin
        trip.destination = input.destination
        trip.earliest_departure = input.earliest_departure
        trip.latest_departure = input.latest_departure
        trip.earliest_return = input.earliest_return
        trip.latest_return = input.latest_return
        trip.latest_departure_time = input.latest_departure_time
        trip.latest_return_time = input.latest_return_time
        await self.session.commit()
        await self.session.refresh(trip)
        return trip

    async def delete_trip(self, trip_id: int) -> bool:
        """Soft-delete a trip request (set is_active=False)."""
        trip = await self.get_trip(trip_id)
        trip.is_active = False
        await self.session.commit()
        return True

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
