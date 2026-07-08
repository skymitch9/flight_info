"""Travelpayouts (Aviasales) cached-price data source.

Free last-resort fallback. Returns *cached* prices from Aviasales search
traffic rather than live availability — data can be hours to days old and
covers economy fares only, but the API is free and effectively unlimited.

To get a token: sign up at https://www.travelpayouts.com, add the
Aviasales/Flights program, and copy the API token from your profile.
"""

import logging
from datetime import date

import httpx

from app.collector.base import FlightDataSource, FlightPrice

logger = logging.getLogger(__name__)

TRAVELPAYOUTS_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


class TravelpayoutsFlightSource(FlightDataSource):
    """Fetches cached flight prices from the Travelpayouts Data API."""

    def __init__(self, token: str):
        self.token = token

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        airline_filter: list[str] | None = None,
    ) -> list[FlightPrice]:
        """Fetch cached one-way prices for a route and date."""
        params = {
            "origin": origin,
            "destination": destination,
            "departure_at": departure_date.isoformat(),
            "one_way": "true",
            "direct": "false",
            "currency": "usd",
            "limit": "30",
            "sorting": "price",
            "token": self.token,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(TRAVELPAYOUTS_URL, params=params, timeout=30.0)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning(
                "Travelpayouts source failed for %s→%s on %s: %s",
                origin, destination, departure_date, str(exc),
            )
            return []

        if not data.get("success"):
            logger.warning(
                "Travelpayouts error for %s→%s: %s",
                origin, destination, data.get("error", "unknown"),
            )
            return []

        results: list[FlightPrice] = []
        for item in data.get("data", []):
            try:
                airline = (item.get("airline") or "").upper()
                flight_number = str(item.get("flight_number", "") or "")
                if airline_filter and airline not in airline_filter:
                    continue
                results.append(
                    FlightPrice(
                        airline=airline or "??",
                        flight_number=f"{airline} {flight_number}".strip(),
                        departure_time=item.get("departure_at", ""),
                        arrival_time="",  # not provided by this endpoint
                        fare_class="main_cabin",  # cached data is economy only
                        price_cents=int(float(item.get("price", 0)) * 100),
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        stops=int(item.get("transfers", 0) or 0),
                        total_duration_minutes=int(item.get("duration", 0) or 0),
                        segments=None,
                    )
                )
            except (KeyError, ValueError, TypeError) as exc:
                logger.debug("Skipping malformed Travelpayouts result: %s", exc)
                continue

        return results

    def supported_airlines(self) -> list[str]:
        """Aviasales cached data covers all airlines."""
        return []
