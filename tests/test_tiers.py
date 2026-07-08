"""Tests for the airline tier engine."""

from datetime import date

from app.tiers.engine import AirlineTier, FlightPrice, TierEngine


def price(airline: str, cents: int, fare_class: str = "main_cabin") -> FlightPrice:
    return FlightPrice(
        airline=airline,
        flight_number=f"{airline}100",
        departure_time="2026-08-28T08:00",
        arrival_time="2026-08-28T11:00",
        fare_class=fare_class,
        price_cents=cents,
        origin="PHX",
        destination="DFW",
        departure_date=date(2026, 8, 28),
    )


class TestClassify:
    def test_tiers(self):
        engine = TierEngine()
        assert engine.classify_airline("DL") == AirlineTier.PRIMARY
        assert engine.classify_airline("AA") == AirlineTier.SECONDARY
        assert engine.classify_airline("NK") == AirlineTier.TERTIARY


class TestFilterOptions:
    def test_empty(self):
        assert TierEngine().filter_options([]) == []

    def test_no_primary_returns_cheapest_three(self):
        prices = [price("NK", 5000), price("F9", 4000), price("B6", 6000), price("AS", 7000)]
        result = TierEngine().filter_options(prices)
        assert [p.price_cents for p in result] == [4000, 5000, 6000]

    def test_secondary_needs_15_percent_discount(self):
        prices = [price("DL", 10000), price("AA", 9000), price("UA", 8000)]
        result = TierEngine().filter_options(prices)
        airlines = [p.airline for p in result]
        assert "DL" in airlines
        assert "UA" in airlines  # 20% cheaper — included
        assert "AA" not in airlines  # only 10% cheaper — excluded

    def test_tertiary_needs_30_percent_discount(self):
        prices = [price("DL", 10000), price("NK", 7500), price("F9", 6500)]
        result = TierEngine().filter_options(prices)
        airlines = [p.airline for p in result]
        assert "F9" in airlines  # 35% cheaper — included
        assert "NK" not in airlines  # 25% cheaper — excluded


class TestPremiumHighlights:
    def test_highlight_within_threshold(self):
        prices = [
            price("DL", 10000),
            price("DL", 13000, "first"),   # within 40% of $100 — highlight
            price("DL", 15000, "business"),  # beyond 40% — excluded
        ]
        result = TierEngine().identify_premium_highlights(prices)
        assert [p.price_cents for p in result] == [13000]

    def test_no_main_cabin_means_no_highlights(self):
        assert TierEngine().identify_premium_highlights([price("DL", 9000, "first")]) == []
