"""Price analysis service using LLM-powered trend evaluation."""

import logging
from datetime import datetime
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.base import FlightPrice
from app.llm.client import LLMClient
from app.models import AnalysisResult as AnalysisResultModel
from app.models import PriceSnapshot, TripRequest

from .prompts import (
    PRICE_ANALYSIS_PROMPT,
    build_current_prices_summary,
    build_price_history_summary,
)

logger = logging.getLogger(__name__)


class Recommendation(str, Enum):
    """Purchase timing recommendation produced by price analysis."""

    BUY_NOW = "buy_now"
    WAIT = "wait"
    PRICES_RISING = "prices_rising"


class PriceAnalyzer:
    """LLM-powered price trend analysis.

    Fetches historical price data, builds a structured prompt,
    sends it to the LLM, and parses the response into a recommendation.
    """

    def __init__(self, llm_client: LLMClient, session_factory):
        """Initialize the PriceAnalyzer.

        Args:
            llm_client: An LLMClient instance for making LLM API calls.
            session_factory: An async session factory for database access.
        """
        self.llm = llm_client
        self.session_factory = session_factory

    async def analyze(
        self, trip: TripRequest, current_prices: list[FlightPrice]
    ) -> AnalysisResultModel | None:
        """Analyze price trends and produce a recommendation.

        Fetches price history for the trip, builds a prompt with context,
        calls the LLM, parses the response, and stores the result.

        Args:
            trip: The TripRequest being analyzed.
            current_prices: Latest collected flight prices for this trip.

        Returns:
            The persisted AnalysisResult model instance, or None when there
            is no price data to analyze.
        """
        # Only prices within this trip's departure window are relevant —
        # route-level collection may include dates for other trips on the route.
        relevant_prices = [
            p
            for p in current_prices
            if trip.earliest_departure <= p.departure_date <= trip.latest_departure
        ]

        async with self.session_factory() as session:
            history = await self._fetch_price_history(session, trip)

            # Nothing to analyze (e.g. trip beyond the booking horizon, or no
            # fares published yet) — don't store a meaningless recommendation.
            if not relevant_prices and not history:
                logger.info(
                    "Skipping analysis for trip %d: no price data in window", trip.id
                )
                return None

            prompt = self._build_prompt(trip, relevant_prices, history)

            try:
                response = await self.llm.complete(prompt)
            except Exception as e:
                logger.error(
                    "LLM API call failed for trip %d: %s", trip.id, e
                )
                # Default to WAIT on LLM failure
                response = ""

            result = self._parse_response(response, trip.id)
            await self._store_result(session, result)
            return result

    async def _fetch_price_history(
        self, session: AsyncSession, trip: TripRequest
    ) -> list[PriceSnapshot]:
        """Fetch relevant price history for a trip, ordered by collection time.

        Snapshots are stored at the route level (trip_request_id is NULL), so
        history is queried by route_id, restricted to main-cabin fares with a
        flight date inside the trip's departure window — the prices the
        recommendation is actually about. Falls back to legacy trip-linked
        snapshots for data collected before route-level storage.

        Args:
            session: The async database session.
            trip: The TripRequest being analyzed.

        Returns:
            List of PriceSnapshot instances ordered by collected_at.
        """
        stmt = (
            select(PriceSnapshot)
            .where(
                PriceSnapshot.route_id == trip.route_id
                if trip.route_id is not None
                else PriceSnapshot.trip_request_id == trip.id
            )
            .where(PriceSnapshot.fare_class == "main_cabin")
            .where(PriceSnapshot.flight_date >= trip.earliest_departure)
            .where(PriceSnapshot.flight_date <= trip.latest_departure)
            .order_by(PriceSnapshot.collected_at)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    def _build_prompt(
        self,
        trip: TripRequest,
        current_prices: list[FlightPrice],
        history: list[PriceSnapshot],
    ) -> str:
        """Build a structured prompt with price history, current prices,
        days until departure, and route context.

        Args:
            trip: The TripRequest being analyzed.
            current_prices: Latest collected flight prices.
            history: Historical price snapshots.

        Returns:
            The formatted prompt string ready for the LLM.
        """
        days_until_departure = (
            trip.earliest_departure - datetime.utcnow().date()
        ).days
        days_until_departure = max(days_until_departure, 0)

        price_history_summary = build_price_history_summary(history)
        current_prices_summary = build_current_prices_summary(current_prices)

        return PRICE_ANALYSIS_PROMPT.format(
            origin=trip.origin,
            destination=trip.destination,
            days_until_departure=days_until_departure,
            price_history_summary=price_history_summary,
            current_prices=current_prices_summary,
        )

    def _parse_response(
        self, response: str, trip_id: int
    ) -> AnalysisResultModel:
        """Parse LLM response into a structured AnalysisResult.

        Looks for recommendation keywords in the response text.
        Defaults to WAIT if the response is unparseable.

        Args:
            response: The raw text response from the LLM.
            trip_id: The trip request ID to associate with the result.

        Returns:
            An AnalysisResult model instance (not yet persisted).
        """
        response_lower = response.lower()

        # Determine recommendation from response keywords
        if "buy_now" in response_lower or "buy now" in response_lower:
            recommendation = Recommendation.BUY_NOW
        elif (
            "prices_rising" in response_lower
            or "prices rising" in response_lower
        ):
            recommendation = Recommendation.PRICES_RISING
        else:
            recommendation = Recommendation.WAIT

        # Extract explanation from response
        explanation = self._extract_explanation(response)

        return AnalysisResultModel(
            trip_request_id=trip_id,
            recommendation=recommendation.value,
            explanation=explanation,
            analyzed_at=datetime.utcnow(),
        )

    def _extract_explanation(self, response: str) -> str:
        """Extract the explanation portion from the LLM response.

        Looks for an 'Explanation:' prefix in the response. Falls back
        to using the full response or a default message.

        Args:
            response: The raw text response from the LLM.

        Returns:
            The extracted explanation string.
        """
        if not response.strip():
            return "Unable to analyze prices at this time."

        # Try to find "Explanation:" in the response
        for line in response.split("\n"):
            stripped = line.strip()
            if stripped.lower().startswith("explanation:"):
                explanation = stripped[len("explanation:"):].strip()
                if explanation:
                    return explanation

        # Fallback: use the full response as explanation if short enough
        if len(response) <= 500:
            return response.strip()

        return response[:500].strip()

    async def _store_result(
        self, session: AsyncSession, result: AnalysisResultModel
    ) -> None:
        """Persist an AnalysisResult to the database.

        Args:
            session: The async database session.
            result: The AnalysisResult model instance to store.
        """
        session.add(result)
        await session.commit()
        await session.refresh(result)
