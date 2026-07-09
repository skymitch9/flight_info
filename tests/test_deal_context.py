"""Tests for deal-context math and phrasing."""

from datetime import datetime, timedelta

from app.analyzer.deal_context import DealContext, compute_deal_context, describe_deal

NOW = datetime(2026, 7, 9, 12, 0, 0)


class Snap:
    def __init__(self, price_cents: int, days_ago: float):
        self.price_cents = price_cents
        self.collected_at = NOW - timedelta(days=days_ago)


class TestComputeDealContext:
    def test_empty_history(self):
        ctx = compute_deal_context([])
        assert ctx.latest_min_cents is None
        assert describe_deal(ctx) is None

    def test_single_batch(self):
        ctx = compute_deal_context([Snap(10000, 0), Snap(12000, 0)], now=NOW)
        assert ctx.latest_min_cents == 10000
        assert ctx.lowest_ever_cents == 10000
        assert ctx.prev_min_cents is None
        assert ctx.is_lowest_ever

    def test_batch_mins_use_cheapest_per_batch(self):
        snaps = [
            Snap(15000, 2), Snap(11000, 2),   # older batch, min 110
            Snap(9000, 0), Snap(14000, 0),    # latest batch, min 90
        ]
        ctx = compute_deal_context(snaps, now=NOW)
        assert ctx.latest_min_cents == 9000
        assert ctx.prev_min_cents == 11000
        assert ctx.lowest_ever_cents == 9000
        assert ctx.is_lowest_ever

    def test_not_lowest_ever(self):
        snaps = [Snap(8000, 5), Snap(10000, 0)]
        ctx = compute_deal_context(snaps, now=NOW)
        assert ctx.lowest_ever_cents == 8000
        assert not ctx.is_lowest_ever

    def test_avg_30d_excludes_older_batches(self):
        snaps = [
            Snap(50000, 60),  # outside the 30-day window
            Snap(10000, 5),
            Snap(12000, 0),
        ]
        ctx = compute_deal_context(snaps, now=NOW)
        assert ctx.avg_30d_cents == 11000


class TestDescribeDeal:
    def test_lowest_ever_and_drop(self):
        text = describe_deal(
            DealContext(
                latest_min_cents=9000,
                prev_min_cents=11000,
                lowest_ever_cents=9000,
                avg_30d_cents=11000,
                is_lowest_ever=True,
            )
        )
        assert "Lowest price ever tracked" in text
        assert "below the 30-day average" in text
        assert "Down $20" in text

    def test_price_rise(self):
        text = describe_deal(
            DealContext(
                latest_min_cents=12000,
                prev_min_cents=10000,
                lowest_ever_cents=9000,
                avg_30d_cents=10000,
                is_lowest_ever=False,
            )
        )
        assert "Up $20" in text
        assert "above the 30-day average" in text

    def test_stable_price_has_no_story(self):
        assert (
            describe_deal(
                DealContext(
                    latest_min_cents=10000,
                    prev_min_cents=10000,
                    lowest_ever_cents=9000,
                    avg_30d_cents=10100,
                    is_lowest_ever=False,
                )
            )
            is None
        )
