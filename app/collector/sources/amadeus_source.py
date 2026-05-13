"""Amadeus Flight Offers Search data source.

Uses the Amadeus Self-Service API to fetch real flight pricing data.
Requires AMADEUS_API_KEY and AMADEUS_API_SECRET environment variables.

To get API credentials:
1. Sign up at https://developers.amadeus.com
2. Create an app in the dashboard
3. Copy the API Key and API Secret
4. Add them to your .env file
"""

import logging
from datetime import date

import httpx

from app.collector.base import FlightDataSource, FlightPrice

logger = logging.getLogger(__name__)

# Amadeus API endpoints
TOKEN_URL_TEST = "https://test.api.amadeus.com/v1/security/oauth2/token"
SEARCH_URL_TEST = "https://test.api.amadeus.com/v2/shopping/flight-offers"
TOKEN_URL_PROD = "https://api.amadeus.com/v1/security/oauth2/token"
SEARCH_URL_PROD = "https://api.amadeus.com/v2/shopping/flight-offers"


class AmadeusFlightSource(FlightDataSource):
    """Fetches flight offers from the Amadeus API.

    Supports both test and production environments. The test environment
    returns realistic but not real-time data (good for development).
    Production returns live pricing.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        use_production: bool = False,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self._access_token: str | None = None

        if use_production:
            self._token_url = TOKEN_URL_PROD
            self._search_url = SEARCH_URL_PROD
        else:
            self._token_url = TOKEN_URL_TEST
            self._search_url = SEARCH_URL_TEST

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        """Authenticate with Amadeus OAuth2 and get an access token."""
        if self._access_token:
            return self._access_token

        response = await client.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.api_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        self._access_token = data["access_token"]
        return self._access_token

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        airline_filter: list[str] | None = None,
    ) -> list[FlightPrice]:
        """Search for flight offers on a given route and date.

        Args:
            origin: 3-letter IATA airport code (e.g., "ATL").
            destination: 3-letter IATA airport code (e.g., "LAX").
            departure_date: Date to search for flights.
            airline_filter: Optional list of airline codes to restrict results.

        Returns:
            List of FlightPrice results from Amadeus.
        """
        async with httpx.AsyncClient() as client:
            try:
                token = await self._get_access_token(client)

                params = {
                    "originLocationCode": origin,
                    "destinationLocationCode": destination,
                    "departureDate": departure_date.isoformat(),
                    "adults": 1,
                    "nonStop": "false",
                    "max": 20,
                    "currencyCode": "USD",
                }

                if airline_filter:
                    params["includedAirlineCodes"] = ",".join(airline_filter)

                response = await client.get(
                    self._search_url,
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30.0,
                )

                # If token expired, refresh and retry once
                if response.status_code == 401:
                    self._access_token = None
                    token = await self._get_access_token(client)
                    response = await client.get(
                        self._search_url,
                        params=params,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=30.0,
                    )

                response.raise_for_status()
                data = response.json()

                return self._parse_offers(data, origin, destination, departure_date)

            except httpx.TimeoutException:
                logger.warning(
                    "Amadeus API timeout for %s→%s on %s",
                    origin, destination, departure_date,
                )
                return []
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Amadeus API error %d for %s→%s: %s",
                    exc.response.status_code, origin, destination,
                    exc.response.text[:200],
                )
                # Clear token on auth errors
                if exc.response.status_code in (401, 403):
                    self._access_token = None
                return []
            except Exception as exc:
                logger.warning(
                    "Amadeus source failed for %s→%s: %s",
                    origin, destination, str(exc),
                )
                return []

    def _parse_offers(
        self,
        data: dict,
        origin: str,
        destination: str,
        departure_date: date,
    ) -> list[FlightPrice]:
        """Parse Amadeus flight offers response into FlightPrice objects."""
        results: list[FlightPrice] = []

        offers = data.get("data", [])
        for offer in offers:
            try:
                price_total = offer.get("price", {}).get("grandTotal", "0")
                price_cents = int(float(price_total) * 100)

                # Each offer can have multiple itineraries (outbound, return)
                # We only care about the first itinerary (outbound)
                itineraries = offer.get("itineraries", [])
                if not itineraries:
                    continue

                first_itinerary = itineraries[0]
                segments = first_itinerary.get("segments", [])
                if not segments:
                    continue

                # Use the first segment for airline/flight info
                first_segment = segments[0]
                last_segment = segments[-1]

                airline_code = first_segment.get("carrierCode", "??")
                flight_number = f"{airline_code}{first_segment.get('number', '0')}"
                departure_time = first_segment.get("departure", {}).get("at", "")
                arrival_time = last_segment.get("arrival", {}).get("at", "")

                # Determine fare class from traveler pricings
                fare_class = self._determine_fare_class(offer)

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
                logger.debug("Skipping malformed offer: %s", exc)
                continue

        return results

    def _determine_fare_class(self, offer: dict) -> str:
        """Determine fare class from Amadeus traveler pricing data.

        Maps Amadeus cabin codes to our internal fare class names.
        """
        traveler_pricings = offer.get("travelerPricings", [])
        if not traveler_pricings:
            return "main_cabin"

        # Check the first traveler's fare details
        fare_details = traveler_pricings[0].get("fareDetailsBySegment", [])
        if not fare_details:
            return "main_cabin"

        cabin = fare_details[0].get("cabin", "ECONOMY").upper()

        cabin_map = {
            "ECONOMY": "main_cabin",
            "PREMIUM_ECONOMY": "comfort_plus",
            "BUSINESS": "business",
            "FIRST": "first",
        }

        return cabin_map.get(cabin, "main_cabin")

    def supported_airlines(self) -> list[str]:
        """Amadeus supports all airlines — return empty to indicate no filter."""
        return []
