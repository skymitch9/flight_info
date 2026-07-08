"""Tests for collection date sampling and the booking-horizon guard.

These guard against the regression where the collector searched "today"
instead of the trip's travel window.
"""

from datetime import date, timedelta

from app.collector.service import CollectionService, sample_dates

TODAY = date.today()


class TripStub:
    def __init__(self, origin, destination, ed, ld, er=None, lr=None):
        self.origin = origin
        self.destination = destination
        self.earliest_departure = ed
        self.latest_departure = ld
        self.earliest_return = er
        self.latest_return = lr


class RouteStub:
    def __init__(self, origin, destination):
        self.origin = origin
        self.destination = destination


def make_service(**kwargs):
    defaults = dict(
        sources=[], session_factory=None, analyzer=None, booking_horizon_days=330
    )
    defaults.update(kwargs)
    return CollectionService(**defaults)


class TestSampleDates:
    def test_small_window_returns_all_dates(self):
        start = TODAY + timedelta(days=10)
        assert sample_dates(start, start + timedelta(days=1), 3) == [
            start,
            start + timedelta(days=1),
        ]

    def test_single_day_window(self):
        start = TODAY + timedelta(days=10)
        assert sample_dates(start, start, 3) == [start]

    def test_large_window_samples_endpoints_and_midpoint(self):
        start = TODAY + timedelta(days=10)
        end = start + timedelta(days=90)
        result = sample_dates(start, end, 3)
        assert len(result) == 3
        assert result[0] == start
        assert result[-1] == end
        assert start < result[1] < end

    def test_past_window_is_empty(self):
        assert sample_dates(TODAY - timedelta(days=30), TODAY - timedelta(days=1), 3) == []

    def test_window_straddling_today_clamps_to_today(self):
        result = sample_dates(TODAY - timedelta(days=10), TODAY + timedelta(days=10), 3)
        assert result and all(d >= TODAY for d in result)

    def test_never_exceeds_max(self):
        start = TODAY + timedelta(days=1)
        assert len(sample_dates(start, start + timedelta(days=365), 5)) <= 5


class TestSearchDatesForRoute:
    def test_outbound_window_in_range(self):
        svc = make_service()
        trip = TripStub("PHX", "DFW", TODAY + timedelta(days=30), TODAY + timedelta(days=31))
        dates = svc._search_dates_for_route(RouteStub("PHX", "DFW"), [trip])
        assert dates == [TODAY + timedelta(days=30), TODAY + timedelta(days=31)]

    def test_never_searches_today_for_future_trips(self):
        """Regression: collector used to search the collection day itself."""
        svc = make_service()
        trip = TripStub("PHX", "DFW", TODAY + timedelta(days=50), TODAY + timedelta(days=52))
        dates = svc._search_dates_for_route(RouteStub("PHX", "DFW"), [trip])
        assert TODAY not in dates
        assert all(trip.earliest_departure <= d <= trip.latest_departure for d in dates)

    def test_beyond_horizon_is_skipped(self):
        svc = make_service()
        far = TODAY + timedelta(days=420)
        trip = TripStub("PHX", "KIX", far, far + timedelta(days=90))
        assert svc._search_dates_for_route(RouteStub("PHX", "KIX"), [trip]) == []

    def test_straddling_horizon_collects_only_in_range(self):
        svc = make_service()
        trip = TripStub(
            "PHX", "ATL", TODAY + timedelta(days=320), TODAY + timedelta(days=360)
        )
        dates = svc._search_dates_for_route(RouteStub("PHX", "ATL"), [trip])
        horizon_end = TODAY + timedelta(days=330)
        assert dates and all(d <= horizon_end for d in dates)

    def test_reverse_route_collects_return_window(self):
        svc = make_service()
        trip = TripStub(
            "PHX", "DFW",
            TODAY + timedelta(days=30), TODAY + timedelta(days=31),
            er=TODAY + timedelta(days=35), lr=TODAY + timedelta(days=36),
        )
        dates = svc._search_dates_for_route(RouteStub("DFW", "PHX"), [trip])
        assert dates == [TODAY + timedelta(days=35), TODAY + timedelta(days=36)]

    def test_one_way_trip_contributes_nothing_to_reverse_route(self):
        svc = make_service()
        trip = TripStub("PHX", "DFW", TODAY + timedelta(days=30), TODAY + timedelta(days=31))
        assert svc._search_dates_for_route(RouteStub("DFW", "PHX"), [trip]) == []

    def test_route_cap_applies(self):
        svc = make_service(max_search_dates_per_route=4)
        trips = [
            TripStub("PHX", "DFW", TODAY + timedelta(days=d), TODAY + timedelta(days=d))
            for d in range(10, 20)
        ]
        assert len(svc._search_dates_for_route(RouteStub("PHX", "DFW"), trips)) == 4

    def test_unrelated_route_contributes_nothing(self):
        svc = make_service()
        trip = TripStub("PHX", "DFW", TODAY + timedelta(days=30), TODAY + timedelta(days=31))
        assert svc._search_dates_for_route(RouteStub("PHX", "ATL"), [trip]) == []
