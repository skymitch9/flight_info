from datetime import date

from app.collector.base import FlightDataSource, FlightPrice


class ExampleFlightSource(FlightDataSource):
    """Reference implementation stub for the FlightDataSource interface.

    This source returns empty results and serves as a template for
    building real data source plugins.
    """

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        airline_filter: list[str] | None = None,
    ) -> list[FlightPrice]:
        """Return an empty list of flights (stub implementation).

        A real implementation would query an external API or scrape
        flight data for the given route and date.
        """
        return []

    def supported_airlines(self) -> list[str]:
        """Return an empty list of supported airlines (stub implementation).

        A real implementation would return the airline codes that this
        source is capable of searching (e.g., ["DL", "AA", "UA"]).
        """
        return []
