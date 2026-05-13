"""Airline Tier Engine - classification, filtering, and premium highlight logic.

Implements tiered airline preference system:
- Primary (Delta): Always included in recommendations
- Secondary (American, United, Southwest): Included if 15%+ cheaper than Primary
- Tertiary (all others): Included if 30%+ cheaper than Primary
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum


class AirlineTier(str, Enum):
    """Priority classification for airlines."""

    PRIMARY = "primary"  # Delta
    SECONDARY = "secondary"  # American, United, Southwest
    TERTIARY = "tertiary"  # All others


# Default configuration (overridable via environment/settings)
DEFAULT_TIER_CONFIG = {
    "primary": ["DL"],  # Delta
    "secondary": ["AA", "UA", "WN"],  # American, United, Southwest
    "secondary_threshold": 0.15,  # 15% cheaper to include
    "tertiary_threshold": 0.30,  # 30% cheaper to include
    "premium_highlight_threshold": 0.40,  # Within 40% of main cabin
}


@dataclass
class FlightPrice:
    """Flight price data used by the tier engine.

    This is a local definition matching the interface from collector/base.py
    (which will be created in task 5.1). Once that module exists, imports
    should be updated to use collector.base.FlightPrice instead.
    """

    airline: str
    flight_number: str
    departure_time: str  # ISO 8601
    arrival_time: str  # ISO 8601
    fare_class: str  # "main_cabin", "business", "first", "comfort_plus"
    price_cents: int
    origin: str
    destination: str
    departure_date: date


class TierEngine:
    """Applies airline tier logic to filter and rank flight options.

    The engine classifies airlines into tiers and uses configurable
    thresholds to determine which non-primary options are worth
    including in recommendations.
    """

    def __init__(self, config: dict | None = None):
        """Initialize with tier configuration.

        Args:
            config: Dictionary with tier settings. Uses DEFAULT_TIER_CONFIG
                    if not provided.
        """
        self.config = config if config is not None else DEFAULT_TIER_CONFIG

    def classify_airline(self, airline_code: str) -> AirlineTier:
        """Determine which tier an airline belongs to.

        Args:
            airline_code: 2-letter IATA airline code (e.g., "DL", "AA").

        Returns:
            The AirlineTier classification for the airline.
        """
        if airline_code in self.config["primary"]:
            return AirlineTier.PRIMARY
        elif airline_code in self.config["secondary"]:
            return AirlineTier.SECONDARY
        return AirlineTier.TERTIARY

    def filter_options(self, prices: list[FlightPrice]) -> list[FlightPrice]:
        """Apply tier thresholds to determine which options to include.

        Returns up to 3 options, prioritizing Primary airline. Secondary
        airlines are included only if they are at least 15% cheaper than
        the best Primary price. Tertiary airlines require a 30% discount.

        If no Primary airline options exist, returns the cheapest 3 options
        regardless of tier.

        Args:
            prices: List of FlightPrice objects to filter (typically
                    main_cabin fares for a given route).

        Returns:
            Up to 3 FlightPrice objects sorted by price, prioritizing Primary.
        """
        if not prices:
            return []

        primary_prices = [
            p for p in prices if self.classify_airline(p.airline) == AirlineTier.PRIMARY
        ]

        # If no primary options, return cheapest 3 regardless of tier
        if not primary_prices:
            return sorted(prices, key=lambda p: p.price_cents)[:3]

        best_primary = min(p.price_cents for p in primary_prices)
        included = list(primary_prices)

        for p in prices:
            tier = self.classify_airline(p.airline)
            if tier == AirlineTier.SECONDARY:
                # Include if at least 15% cheaper than best primary
                if p.price_cents <= best_primary * (1 - self.config["secondary_threshold"]):
                    included.append(p)
            elif tier == AirlineTier.TERTIARY:
                # Include if at least 30% cheaper than best primary
                if p.price_cents <= best_primary * (1 - self.config["tertiary_threshold"]):
                    included.append(p)

        return sorted(included, key=lambda p: p.price_cents)[:3]

    def identify_premium_highlights(self, prices: list[FlightPrice]) -> list[FlightPrice]:
        """Find premium fares within threshold of main cabin price.

        Identifies upgrade opportunities where a premium fare (business,
        first, comfort_plus) is within 40% of the cheapest main cabin fare.

        Args:
            prices: List of FlightPrice objects across all fare classes.

        Returns:
            List of premium FlightPrice objects that qualify as highlights.
        """
        main_cabin = [p for p in prices if p.fare_class == "main_cabin"]
        premium = [p for p in prices if p.fare_class != "main_cabin"]

        if not main_cabin:
            return []

        best_main = min(p.price_cents for p in main_cabin)
        threshold = best_main * (1 + self.config["premium_highlight_threshold"])

        return [p for p in premium if p.price_cents <= threshold]
