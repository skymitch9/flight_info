"""SerpAPI Google Flights data source.

Uses SerpAPI to scrape Google Flights results for real flight pricing data.
Requires a SERPAPI_KEY environment variable.

To get your API key:
1. Sign up at https://serpapi.com/users/sign_up (free tier: 250 searches/month)
2. Go to your dashboard → API Key
3. Copy the key and add it to your .env file as SERPAPI_KEY
"""

import logging
from datetime import date

import httpx

from app.collector.base import FlightDataSource, FlightPrice

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"


class SerpAPIFlightSource(FlightDataSource):
    """Fetches flight data from Google Flights via SerpAPI.

    Returns real pricing data scraped from Google Flights.
    Free tier: 250 searches/month (plenty for a personal tracker).
    """

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
        """Search Google Flights for a given route and date across specified fare classes.

        Args:
            origin: 3-letter IATA airport code (e.g., "ATL").
            destination: 3-letter IATA airport code (e.g., "LAX").
            departure_date: Date to search for flights.
            airline_filter: Optional list of airline codes to restrict results.
            travel_classes: List of travel class codes to query.
                1=Economy, 2=Premium Economy, 3=Business, 4=First.
                Defaults to [1] (economy only).

        Returns:
            List of FlightPrice results from Google Flights across specified travel classes.
        """
        if travel_classes is None:
            travel_classes = self._travel_classes

        all_results: list[FlightPrice] = []

        async with httpx.AsyncClient() as client:
            for travel_class in travel_classes:
                try:
                    params = {
                        "engine": "google_flights",
                        "departure_id": origin,
                        "arrival_id": destination,
                        "outbound_date": departure_date.isoformat(),
                        "currency": "USD",
                        "hl": "en",
                        "type": "2",  # One-way
                        "travel_class": str(travel_class),
                        "api_key": self.api_key,
                    }

                    # Add airline filter if specified
                    if airline_filter:
                        params["include_airlines"] = ",".join(airline_filter)

                    response = await client.get(
                        SERPAPI_URL,
                        params=params,
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Check for API errors
                    if "error" in data:
                        logger.warning(
                            "SerpAPI error for %s→%s (class %d): %s",
                            origin, destination, travel_class, data["error"],
                        )
                        continue

                    results = self._parse_results(data, origin, destination, departure_date, travel_class)
                    all_results.extend(results)

                except httpx.TimeoutException:
                    logger.warning(
                        "SerpAPI timeout for %s→%s (class %d) on %s",
                        origin, destination, travel_class, departure_date,
                    )
                    continue
                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "SerpAPI HTTP error %d for %s→%s (class %d): %s",
                        exc.response.status_code, origin, destination, travel_class,
                        exc.response.text[:200],
                    )
                    continue
                except Exception as exc:
                    logger.warning(
                        "SerpAPI source failed for %s→%s (class %d): %s",
                        origin, destination, travel_class, str(exc),
                    )
                    continue

        return all_results

    def _parse_results(
        self,
        data: dict,
        origin: str,
        destination: str,
        departure_date: date,
        travel_class: int = 1,
    ) -> list[FlightPrice]:
        """Parse SerpAPI Google Flights response into FlightPrice objects."""
        from app.collector.base import FlightSegment

        results: list[FlightPrice] = []

        # Map travel_class number to fare class string
        fare_class_map = {
            1: "main_cabin",
            2: "premium_economy",
            3: "business",
            4: "first",
        }
        fare_class = fare_class_map.get(travel_class, "main_cabin")

        # Google Flights returns "best_flights" and "other_flights"
        all_flights = []
        all_flights.extend(data.get("best_flights", []))
        all_flights.extend(data.get("other_flights", []))

        for flight_group in all_flights:
            try:
                price = flight_group.get("price")
                if not price:
                    continue

                price_cents = int(float(price) * 100)

                # Each flight group has "flights" (segments)
                segments_data = flight_group.get("flights", [])
                if not segments_data:
                    continue

                first_segment = segments_data[0]
                last_segment = segments_data[-1]

                # Extract airline info
                airline_code = first_segment.get("airline", "")
                flight_number = first_segment.get("flight_number", "")
                if not flight_number and "flight_number" in first_segment:
                    flight_number = str(first_segment["flight_number"])

                # Departure and arrival info
                departure_info = first_segment.get("departure_airport", {})
                arrival_info = last_segment.get("arrival_airport", {})

                departure_time = departure_info.get("time", "")
                arrival_time = arrival_info.get("time", "")

                # Use the fare class from the travel_class parameter
                # (already determined above from the API request)

                # Build a reasonable flight number
                if not flight_number:
                    flight_number = f"{airline_code}000"

                # Use 2-letter airline code if we got a full name
                if len(airline_code) > 2:
                    if flight_number and len(flight_number) >= 2:
                        airline_code = flight_number[:2]
                    else:
                        airline_code = airline_code[:2].upper()

                # Stops and duration
                stops = len(segments_data) - 1
                total_duration = flight_group.get("total_duration", 0)

                # Build segment details
                segments: list[FlightSegment] = []
                for seg in segments_data:
                    seg_dep = seg.get("departure_airport", {})
                    seg_arr = seg.get("arrival_airport", {})
                    segments.append(FlightSegment(
                        airline=seg.get("airline", airline_code),
                        flight_number=seg.get("flight_number", ""),
                        origin=seg_dep.get("id", seg_dep.get("name", "")),
                        destination=seg_arr.get("id", seg_arr.get("name", "")),
                        departure_time=seg_dep.get("time", ""),
                        arrival_time=seg_arr.get("time", ""),
                        duration_minutes=seg.get("duration", 0),
                    ))

                results.append(
                    FlightPrice(
                        airline=airline_code,
                        flight_number=flight_number,
                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        fare_class=fare_class,
                        price_cents=price_cents,
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        stops=stops,
                        total_duration_minutes=total_duration,
                        segments=segments,
                    )
                )
            except (KeyError, ValueError, TypeError) as exc:
                logger.debug("Skipping malformed flight result: %s", exc)
                continue

        return results

    def _determine_fare_class(self, flight_group: dict) -> str:
        """Determine fare class from Google Flights data.

        Google Flights shows travel class in the flight group.
        """
        # Check for explicit travel class
        travel_class = flight_group.get("travel_class", "").upper()

        if "BUSINESS" in travel_class:
            return "business"
        elif "FIRST" in travel_class:
            return "first"
        elif "PREMIUM" in travel_class:
            return "comfort_plus"

        # Default to main cabin (economy)
        return "main_cabin"

    def supported_airlines(self) -> list[str]:
        """Google Flights supports all airlines."""
        return []
