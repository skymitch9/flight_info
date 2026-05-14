"""Price calculator for passenger and luggage pricing.

Computes all-in total price: (base_fare + bag_fees_per_passenger) × passenger_count.
All values are in cents (USD) using integer arithmetic.
"""

from dataclasses import dataclass

from app.pricing.bag_fees import AirlineBagFees, BAG_FEE_SCHEDULE


@dataclass
class LuggageConfig:
    """Luggage requirements per passenger.

    Attributes:
        carry_on_bags: Number of carry-on bags per passenger (0-2).
        checked_bags: Number of checked bags per passenger (0-5).
    """

    carry_on_bags: int
    checked_bags: int


@dataclass
class PriceBreakdown:
    """Breakdown of the computed total price.

    Attributes:
        base_fare_cents: The per-seat base fare in cents (clamped to >= 0).
        bag_fees_per_passenger_cents: Total bag fees for one passenger in cents.
        passenger_count: Number of passengers in the party.
        total_price_cents: All-in price = (base_fare + bag_fees) * passenger_count.
    """

    base_fare_cents: int
    bag_fees_per_passenger_cents: int
    passenger_count: int
    total_price_cents: int


def get_bag_fees_per_passenger(airline_code: str, luggage: LuggageConfig) -> int:
    """Return total bag fees in cents for one passenger.

    Looks up the airline in BAG_FEE_SCHEDULE. If not found, all fees are 0.
    Carry-on fee is charged per carry-on bag. Checked bag fees are positional:
    the first bag uses index 0, the second uses index 1, etc. If the passenger
    has more checked bags than entries in the list, the last entry's fee is
    used for additional bags.

    Args:
        airline_code: IATA airline code (e.g. "DL", "NK").
        luggage: Luggage configuration per passenger.

    Returns:
        Total bag fees in cents for one passenger.
    """
    fees: AirlineBagFees | None = BAG_FEE_SCHEDULE.get(airline_code)
    if fees is None:
        return 0

    # Carry-on fees
    carry_on_total = fees.carry_on_fee_cents * luggage.carry_on_bags

    # Checked bag fees (positional)
    checked_total = 0
    checked_fee_list = fees.checked_bag_fees_cents
    for i in range(luggage.checked_bags):
        if checked_fee_list:
            if i < len(checked_fee_list):
                checked_total += checked_fee_list[i]
            else:
                # Use the last entry's fee for additional bags
                checked_total += checked_fee_list[-1]

    return carry_on_total + checked_total


def calculate_total_price(
    base_fare_cents: int,
    airline_code: str,
    luggage: LuggageConfig,
    passenger_count: int,
) -> PriceBreakdown:
    """Compute the all-in price for the travel party.

    Pure function with no side effects. Clamps negative base fares to 0.
    For multi-segment flights, the caller should pass the first segment's
    airline code.

    Args:
        base_fare_cents: Per-seat base fare in cents.
        airline_code: IATA airline code for fee lookup.
        luggage: Luggage configuration per passenger.
        passenger_count: Number of passengers in the party.

    Returns:
        A PriceBreakdown with the computed total price.
    """
    # Clamp negative base fares to 0
    clamped_base_fare = max(base_fare_cents, 0)

    bag_fees = get_bag_fees_per_passenger(airline_code, luggage)
    total = (clamped_base_fare + bag_fees) * passenger_count

    return PriceBreakdown(
        base_fare_cents=clamped_base_fare,
        bag_fees_per_passenger_cents=bag_fees,
        passenger_count=passenger_count,
        total_price_cents=total,
    )
