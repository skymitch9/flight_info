"""Prompt templates for LLM-powered price analysis."""

PRICE_ANALYSIS_PROMPT = """\
You are a flight price analyst. Analyze the following flight pricing data and provide a purchase timing recommendation.

## Route
{origin} → {destination}

## Days Until Departure
{days_until_departure} days

## Price History Summary
{price_history_summary}

## Current Prices
{current_prices}

## Instructions
Based on the price history trends, current prices, and days until departure, provide:
1. A recommendation: one of "buy_now", "wait", or "prices_rising"
2. A brief explanation (2-3 sentences) of why you made this recommendation

Consider these factors:
- If prices are at or near historical lows, recommend "buy_now"
- If prices are trending upward and departure is approaching, recommend "prices_rising"
- If prices are stable or trending down with time remaining, recommend "wait"
- Closer departure dates (< 14 days) should bias toward "buy_now" or "prices_rising"

Format your response as:
Recommendation: <buy_now|wait|prices_rising>
Explanation: <your explanation>
"""


def build_price_history_summary(snapshots: list) -> str:
    """Build a human-readable summary of price history from snapshot records.

    Args:
        snapshots: List of PriceSnapshot model instances ordered by collected_at.

    Returns:
        A formatted string summarizing price trends.
    """
    if not snapshots:
        return "No historical price data available."

    prices = [s.price_cents for s in snapshots]
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)
    latest_price = prices[-1]

    lines = [
        f"- Number of data points: {len(snapshots)}",
        f"- Lowest observed price: ${min_price / 100:.2f}",
        f"- Highest observed price: ${max_price / 100:.2f}",
        f"- Average price: ${avg_price / 100:.2f}",
        f"- Most recent price: ${latest_price / 100:.2f}",
    ]

    # Add trend indicator
    if len(prices) >= 3:
        recent = prices[-3:]
        if recent[-1] > recent[0]:
            lines.append("- Trend: Prices are rising")
        elif recent[-1] < recent[0]:
            lines.append("- Trend: Prices are falling")
        else:
            lines.append("- Trend: Prices are stable")

    return "\n".join(lines)


def build_current_prices_summary(current_prices: list) -> str:
    """Build a human-readable summary of current flight prices.

    Args:
        current_prices: List of FlightPrice dataclass instances.

    Returns:
        A formatted string listing current available flights and prices.
    """
    if not current_prices:
        return "No current price data available."

    lines = []
    for price in current_prices:
        lines.append(
            f"- {price.airline} {price.flight_number}: "
            f"${price.price_cents / 100:.2f} ({price.fare_class}) "
            f"dep {price.departure_time}"
        )

    return "\n".join(lines)
