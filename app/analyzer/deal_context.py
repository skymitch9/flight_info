"""Deal context: how good is the current price relative to tracked history.

Pure functions over price snapshots — no I/O — so alerts, the digest, and
tests can all share the same math.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class DealContext:
    """Summary of the latest price against tracked history."""

    latest_min_cents: int | None = None
    prev_min_cents: int | None = None  # previous collection batch
    lowest_ever_cents: int | None = None
    avg_30d_cents: int | None = None
    is_lowest_ever: bool = False


def _batch_mins(snapshots) -> list[tuple[datetime, int]]:
    """Cheapest fare per collection batch, oldest first.

    Batches are runs of snapshots whose collected_at fall within 5 minutes
    of the batch start — the same batching used elsewhere in the app.
    """
    ordered = sorted(snapshots, key=lambda s: s.collected_at)
    batches: list[tuple[datetime, int]] = []
    batch_start: datetime | None = None
    batch_min: int | None = None

    for snap in ordered:
        if batch_start is None or snap.collected_at - batch_start > timedelta(minutes=5):
            if batch_start is not None:
                batches.append((batch_start, batch_min))
            batch_start = snap.collected_at
            batch_min = snap.price_cents
        else:
            batch_min = min(batch_min, snap.price_cents)
    if batch_start is not None:
        batches.append((batch_start, batch_min))

    return batches


def compute_deal_context(snapshots, now: datetime | None = None) -> DealContext:
    """Build a DealContext from snapshots of comparable fares.

    Callers pass snapshots already filtered to what the user would actually
    book: main cabin, within the trip's travel window, honoring the trip's
    max-stops preference.
    """
    if not snapshots:
        return DealContext()

    now = now or datetime.utcnow()
    batches = _batch_mins(snapshots)
    latest_min = batches[-1][1]
    prev_min = batches[-2][1] if len(batches) >= 2 else None
    lowest_ever = min(m for _, m in batches)

    cutoff = now - timedelta(days=30)
    recent = [m for t, m in batches if t >= cutoff]
    avg_30d = round(sum(recent) / len(recent)) if recent else None

    return DealContext(
        latest_min_cents=latest_min,
        prev_min_cents=prev_min,
        lowest_ever_cents=lowest_ever,
        avg_30d_cents=avg_30d,
        is_lowest_ever=latest_min <= lowest_ever,
    )


def describe_deal(ctx: DealContext) -> str | None:
    """Human-readable one-liner for emails, or None when there's no story.

    Examples: "Lowest price ever tracked — 12% below the 30-day average.",
    "Down $23 since the last check."
    """
    if ctx.latest_min_cents is None:
        return None

    parts: list[str] = []

    if ctx.is_lowest_ever and ctx.prev_min_cents is not None:
        parts.append("Lowest price ever tracked")

    if ctx.avg_30d_cents:
        diff_pct = (ctx.latest_min_cents - ctx.avg_30d_cents) / ctx.avg_30d_cents
        if diff_pct <= -0.03:
            parts.append(f"{abs(diff_pct) * 100:.0f}% below the 30-day average")
        elif diff_pct >= 0.03:
            parts.append(f"{diff_pct * 100:.0f}% above the 30-day average")

    if ctx.prev_min_cents is not None and ctx.prev_min_cents != ctx.latest_min_cents:
        delta = ctx.latest_min_cents - ctx.prev_min_cents
        direction = "Down" if delta < 0 else "Up"
        parts.append(f"{direction} ${abs(delta) / 100:.0f} since the last check")

    if not parts:
        return None
    return " — ".join(parts) + "."
