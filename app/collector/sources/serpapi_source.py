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

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        airline_filter: list[str] | None = None,
    ) -> list[FlightPrice]:
        """Search Google Flights for a given route and date.

        Args:
            origin: 3-letter IATA airport code (e.g., "ATL").
            destination: 3-letter IATA airport code (e.g., "LAX").
            departure_date: Date to search for flights.
            airline_filter: Optional list of airline codes to restrict results.

        Returns:
            List of FlightPrice results from Google Flights.
        """
        async with httpx.AsyncClient() as client:
            try:
                params = {
                    "engine": "google_flights",
                    "departure_id": origin,
                    "arrival_id": destination,
                    "outbound_date": departure_date.isoformat(),
                    "currency": "USD",
                    "hl": "en",
                    "type": "2",  # One-way (simpler for price tracking)
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
                        "SerpAPI error for %s→%s: %s",
                        origin, destination, data["error"],
                    )
                    return []

                return self._parse_results(data, origin, destination, departure_date)

            except httpx.TimeoutException:
                logger.warning(
                    "SerpAPI timeout for %s→%s on %s",
                    origin, destination, departure_date,
                )
                return []
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "SerpAPI HTTP error %d for %s→%s: %s",
                    exc.response.status_code, origin, destination,
                    exc.response.text[:200],
                )
                return []
            except Exception as exc:
                logger.warning(
                    "SerpAPI source failed for %s→%s: %s",
                    origin, destination, str(exc),
                )
                return []

    def _parse_results(
        self,
        data: dict,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> list[FlightPrice]:
        """Parse SerpAPI Google Flights response into FlightPrice objects."""
        results: list[FlightPrice] = []

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
                segments = flight_group.get("flights", [])
                if not segments:
                    continue

                first_segment = segments[0]
                last_segment = segments[-1]

                # Extract airline info
                airline_code = first_segment.get("airline", "")
                # SerpAPI sometimes gives full name, sometimes code
                # Try to get the airline logo URL which contains the code
                airline_logo = first_segment.get("airline_logo", "")

                flight_number = first_segment.get("flight_number", "")
                if not flight_number and "flight_number" in first_segment:
                    flight_number = str(first_segment["flight_number"])

                # Departure and arrival info
                departure_info = first_segment.get("departure_airport", {})
                arrival_info = last_segment.get("arrival_airport", {})

                departure_time = departure_info.get("time", "")
                arrival_time = arrival_info.get("time", "")

                # Determine fare class from type/class info
                fare_class = self._determine_fare_class(flight_group)

                # Build a reasonable flight number
                if not flight_number:
                    flight_number = f"{airline_code}000"

                # Use 2-letter airline code if we got a full name
                if len(airline_code) > 2:
                    # Try to extract from flight number
                    if flight_number and len(flight_number) >= 2:
                        airline_code = flight_number[:2]
                    else:
                        airline_code = airline_code[:2].upper()

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
