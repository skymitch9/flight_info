from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class FlightSegment:
    """A single leg/segment of a flight."""

    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    duration_minutes: int


@dataclass
class FlightPrice:
    """Represents a single flight price result from a data source."""

    airline: str
    flight_number: str
    departure_time: str  # ISO 8601
    arrival_time: str  # ISO 8601
    fare_class: str  # "main_cabin", "business", "first", "comfort_plus"
    price_cents: int
    origin: str
    destination: str
    departure_date: date
    stops: int = 0
    total_duration_minutes: int = 0
    segments: list[FlightSegment] | None = None


class FlightDataSource(ABC):
    """Plugin interface for airline data providers.

    New data sources implement this interface and are registered
    in the application configuration. No core logic changes needed.
    """

    @abstractmethod
    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        airline_filter: list[str] | None = None,
    ) -> list[FlightPrice]:
        """Search for flights on a given route and date.

        Args:
            origin: 3-letter IATA airport code.
            destination: 3-letter IATA airport code.
            departure_date: Date to search for flights.
            airline_filter: Optional list of airline codes to restrict results.

        Returns:
            List of FlightPrice results matching the search criteria.
        """
        ...

    @abstractmethod
    def supported_airlines(self) -> list[str]:
        """Return list of airline codes this source can search."""
        ...
