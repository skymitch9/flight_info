"""SearchAPI.io Google Flights data source.

Fallback source with near-identical data quality to SerpAPI (both scrape
Google Flights). Free tier: 100 requests. Requires SEARCHAPI_KEY.

To get an API key: sign up at https://www.searchapi.io and copy the key
from the dashboard.
"""

import logging
from datetime import date

import httpx

from app.collector.base import FlightDataSource, FlightPrice, FlightSegment

logger = logging.getLogger(__name__)

SEARCHAPI_URL = "https://www.searchapi.io/api/v1/search"


class SearchAPIFlightSource(FlightDataSource):
    """Fetches flight data from Google Flights via SearchAPI.io."""

    def __init__(self, api_key: str, travel_classes: list[int] | None = None):
        self.api_key = api_key
        self._travel_classes = travel_classes or [1]

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        airline_filter: list[str] | None = None,
        travel_classes: list[int] | None = None,
    ) -> list[FlightPrice]:
        """Search Google Flights for a route/date across the configured fare classes."""
        if travel_classes is None:
            travel_classes = self._travel_classes

        all_results: list[FlightPrice] = []

        async with httpx.AsyncClient() as client:
            for travel_class in travel_classes:
                try:
                    params = {
                        "engine": "google_flights",
                        "flight_type": "one_way",
                        "departure_id": origin,
                        "arrival_id": destination,
                        "outbound_date": departure_date.isoformat(),
                        "currency": "USD",
                        "travel_class": self._travel_class_name(travel_class),
                        "api_key": self.api_key,
                    }
                    response = await client.get(SEARCHAPI_URL, params=params, timeout=30.0)
                    response.raise_for_status()
                    data = response.json()

                    if "error" in data:
                        logger.warning(
                            "SearchAPI error for %s→%s (class %d): %s",
                            origin, destination, travel_class, data["error"],
                        )
                        continue

                    all_results.extend(
                        self._parse_results(data, origin, destination, departure_date, travel_class)
                    )
                except Exception as exc:
                    logger.warning(
                        "SearchAPI source failed for %s→%s (class %d): %s",
                        origin, destination, travel_class, str(exc),
                    )
                    continue

        return all_results

    @staticmethod
    def _travel_class_name(travel_class: int) -> str:
        return {1: "economy", 2: "premium_economy", 3: "business", 4: "first"}.get(
            travel_class, "economy"
        )

    def _parse_results(
        self,
        data: dict,
        origin: str,
        destination: str,
        departure_date: date,
        travel_class: int,
    ) -> list[FlightPrice]:
        """Parse a SearchAPI google_flights response into FlightPrice objects.

        The response shape mirrors SerpAPI's: flight groups under
        "best_flights" / "other_flights", each with a "flights" segment list
        and a top-level "price".
        """
        fare_class = {
            1: "main_cabin",
            2: "premium_economy",
            3: "business",
            4: "first",
        }.get(travel_class, "main_cabin")

        results: list[FlightPrice] = []
        all_flights = list(data.get("best_flights", [])) + list(data.get("other_flights", []))

        for flight_group in all_flights:
            try:
                price = flight_group.get("price")
                segments_data = flight_group.get("flights", [])
                if not price or not segments_data:
                    continue

                price_cents = int(float(price) * 100)
                first_segment = segments_data[0]
                last_segment = segments_data[-1]

                airline_code = first_segment.get("airline", "")
                flight_number = str(first_segment.get("flight_number", "") or "")
                if not flight_number:
                    flight_number = f"{airline_code}000"
                if len(airline_code) > 2:
                    airline_code = (
                        flight_number[:2] if len(flight_number) >= 2 else airline_code[:2].upper()
                    )

                departure_info = first_segment.get("departure_airport", {})
                arrival_info = last_segment.get("arrival_airport", {})

                segments: list[FlightSegment] = []
                for seg in segments_data:
                    seg_dep = seg.get("departure_airport", {})
                    seg_arr = seg.get("arrival_airport", {})
                    segments.append(
                        FlightSegment(
                            airline=seg.get("airline", airline_code),
                            flight_number=str(seg.get("flight_number", "") or ""),
                            origin=seg_dep.get("id", seg_dep.get("name", "")),
                            destination=seg_arr.get("id", seg_arr.get("name", "")),
                            departure_time=seg_dep.get("time", ""),
                            arrival_time=seg_arr.get("time", ""),
                            duration_minutes=seg.get("duration", 0),
                        )
                    )

                results.append(
                    FlightPrice(
                        airline=airline_code,
                        flight_number=flight_number,
                        departure_time=departure_info.get("time", ""),
                        arrival_time=arrival_info.get("time", ""),
                        fare_class=fare_class,
                        price_cents=price_cents,
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        stops=len(segments_data) - 1,
                        total_duration_minutes=flight_group.get("total_duration", 0),
                        segments=segments,
                    )
                )
            except (KeyError, ValueError, TypeError) as exc:
                logger.debug("Skipping malformed SearchAPI flight result: %s", exc)
                continue

        return results

    def supported_airlines(self) -> list[str]:
        """Google Flights supports all airlines."""
        return []
