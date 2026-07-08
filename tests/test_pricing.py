"""Tests for the price calculator (bag fees × passengers)."""

from app.pricing.calculator import LuggageConfig, calculate_total_price, get_bag_fees_per_passenger


class TestCalculateTotalPrice:
    def test_no_bags_single_passenger(self):
        result = calculate_total_price(10000, "DL", LuggageConfig(0, 0), 1)
        assert result.total_price_cents == 10000

    def test_passenger_multiplication(self):
        result = calculate_total_price(10000, "DL", LuggageConfig(0, 0), 3)
        assert result.total_price_cents == 30000

    def test_negative_fare_clamped_to_zero(self):
        result = calculate_total_price(-500, "DL", LuggageConfig(0, 0), 1)
        assert result.base_fare_cents == 0
        assert result.total_price_cents >= 0

    def test_unknown_airline_has_zero_fees(self):
        assert get_bag_fees_per_passenger("ZZ", LuggageConfig(2, 5)) == 0

    def test_bag_fees_added_per_passenger(self):
        fees = get_bag_fees_per_passenger("NK", LuggageConfig(1, 1))
        result = calculate_total_price(10000, "NK", LuggageConfig(1, 1), 2)
        assert result.total_price_cents == (10000 + fees) * 2
        assert result.bag_fees_per_passenger_cents == fees
