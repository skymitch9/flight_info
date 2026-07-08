"""Tests for trip input validation rules."""

from datetime import date, timedelta

import pytest

from app.trip_manager.service import TripInput, TripService, TripValidationError

TOMORROW = date.today() + timedelta(days=1)
NEXT_WEEK = date.today() + timedelta(days=7)


def make_input(**overrides) -> TripInput:
    defaults = dict(
        origin="PHX",
        destination="DFW",
        earliest_departure=TOMORROW,
        latest_departure=NEXT_WEEK,
    )
    defaults.update(overrides)
    return TripInput(**defaults)


def validate(input: TripInput) -> None:
    TripService(session=None)._validate(input)


class TestValidation:
    def test_valid_input_passes(self):
        validate(make_input())

    @pytest.mark.parametrize("code", ["", "PH", "PHXX", "phx", "P1X"])
    def test_bad_iata_codes_rejected(self, code):
        with pytest.raises(TripValidationError):
            validate(make_input(origin=code))

    def test_past_departure_rejected(self):
        with pytest.raises(TripValidationError):
            validate(make_input(earliest_departure=date.today() - timedelta(days=1)))

    def test_inverted_departure_range_rejected(self):
        with pytest.raises(TripValidationError):
            validate(make_input(latest_departure=TOMORROW - timedelta(days=1)))

    def test_return_before_departure_rejected(self):
        with pytest.raises(TripValidationError):
            validate(make_input(earliest_return=TOMORROW - timedelta(days=1)))

    def test_latest_return_requires_earliest_return(self):
        with pytest.raises(TripValidationError):
            validate(make_input(latest_return=NEXT_WEEK))

    @pytest.mark.parametrize("count", [0, 10])
    def test_passenger_count_bounds(self, count):
        with pytest.raises(TripValidationError):
            validate(make_input(passenger_count=count))

    def test_zero_target_price_rejected(self):
        with pytest.raises(TripValidationError):
            validate(make_input(target_price_cents=0))

    def test_valid_target_price_passes(self):
        validate(make_input(target_price_cents=15000))

    def test_none_target_price_passes(self):
        validate(make_input(target_price_cents=None))
