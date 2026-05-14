"""Airline bag fee schedule.

Contains per-airline fees for carry-on and checked bags.
All values are in cents (USD).
"""

from dataclasses import dataclass, field


@dataclass
class AirlineBagFees:
    """Fee structure for a single airline's bag charges.

    Attributes:
        carry_on_fee_cents: Fee in cents per carry-on bag.
        checked_bag_fees_cents: List of fees in cents for checked bags,
            where index 0 = first bag fee, index 1 = second bag fee, etc.
    """

    carry_on_fee_cents: int
    checked_bag_fees_cents: list[int] = field(default_factory=list)


BAG_FEE_SCHEDULE: dict[str, AirlineBagFees] = {
    "AA": AirlineBagFees(
        carry_on_fee_cents=0,
        checked_bag_fees_cents=[3500, 4500],
    ),
    "DL": AirlineBagFees(
        carry_on_fee_cents=0,
        checked_bag_fees_cents=[3500, 4500],
    ),
    "UA": AirlineBagFees(
        carry_on_fee_cents=0,
        checked_bag_fees_cents=[3500, 4500],
    ),
    "WN": AirlineBagFees(
        carry_on_fee_cents=0,
        checked_bag_fees_cents=[0, 0],
    ),
    "NK": AirlineBagFees(
        carry_on_fee_cents=4500,
        checked_bag_fees_cents=[4900, 5900],
    ),
    "F9": AirlineBagFees(
        carry_on_fee_cents=5000,
        checked_bag_fees_cents=[4500, 5500],
    ),
    "B6": AirlineBagFees(
        carry_on_fee_cents=0,
        checked_bag_fees_cents=[3500, 4500],
    ),
    "AS": AirlineBagFees(
        carry_on_fee_cents=0,
        checked_bag_fees_cents=[3500, 4500],
    ),
    "HA": AirlineBagFees(
        carry_on_fee_cents=0,
        checked_bag_fees_cents=[3500, 4500],
    ),
    "SY": AirlineBagFees(
        carry_on_fee_cents=4500,
        checked_bag_fees_cents=[4000, 5000],
    ),
    "G4": AirlineBagFees(
        carry_on_fee_cents=4500,
        checked_bag_fees_cents=[4500, 5500],
    ),
}
