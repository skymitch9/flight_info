# Implementation Plan: Passenger and Luggage Pricing

## Overview

Add passenger count and luggage inputs to trip contracts, implement an airline bag fee schedule, build a price calculator that computes all-in total prices, extend the GraphQL API, and update the frontend form and flight options display.

## Tasks

- [x] 1. Database migration and model update
  - [x] 1.1 Add passenger and luggage columns to the TripRequest model
    - Add `passenger_count`, `carry_on_bags`, and `checked_bags` columns to `TripRequest` in `app/models.py`
    - Set defaults: passenger_count=1, carry_on_bags=1, checked_bags=0
    - _Requirements: 1.4, 2.6, 7.1, 7.2, 7.3_

  - [x] 1.2 Create Alembic migration for new columns
    - Generate migration adding `passenger_count INTEGER NOT NULL DEFAULT 1`, `carry_on_bags INTEGER NOT NULL DEFAULT 1`, `checked_bags INTEGER NOT NULL DEFAULT 0` to `trip_requests`
    - Add CHECK constraints for valid ranges (passenger_count 1-9, carry_on_bags 0-2, checked_bags 0-5)
    - _Requirements: 1.2, 2.3, 2.4, 7.1, 7.2, 7.3_

- [x] 2. Bag fee schedule and price calculator
  - [x] 2.1 Create the bag fee schedule module (`app/pricing/bag_fees.py`)
    - Define `AirlineBagFees` dataclass with `carry_on_fee_cents` and `checked_bag_fees_cents` fields
    - Populate `BAG_FEE_SCHEDULE` dict with entries for major airlines (DL, AA, UA, WN, NK, F9, etc.)
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 2.2 Create the price calculator module (`app/pricing/calculator.py`)
    - Define `LuggageConfig` and `PriceBreakdown` dataclasses
    - Implement `calculate_total_price(base_fare_cents, airline_code, luggage, passenger_count)` returning a `PriceBreakdown`
    - Implement `get_bag_fees_per_passenger(airline_code, luggage)` using the bag fee schedule
    - Handle unknown airline codes by returning 0 fees, clamp negative base fares to 0
    - For multi-segment flights, use the first segment's airline code
    - _Requirements: 3.5, 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 3. Backend service and GraphQL API updates
  - [x] 3.1 Update TripInput and TripService to handle new fields
    - Add `passenger_count`, `carry_on_bags`, `checked_bags` to `TripInput` dataclass in `app/trip_manager/service.py`
    - Update `_validate` to enforce range constraints (passenger_count 1-9, carry_on_bags 0-2, checked_bags 0-5)
    - Update `create_trip` and `update_trip` to persist the new fields
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 3.2 Extend GraphQL schema with passenger, luggage, and pricing fields
    - Add optional `passenger_count`, `carry_on_bags`, `checked_bags` fields to `TripRequestInput` with defaults (1, 1, 0)
    - Expose `passenger_count`, `carry_on_bags`, `checked_bags` on `TripRequestType`
    - Add `total_price_cents` field to `FlightOptionType` resolved via `PriceCalculator`
    - Add `total_combined_price_cents` field to `RoundTripOptionType`
    - Wire the resolver to use the trip's luggage config and passenger count when computing totals
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [x] 4. Frontend form and display updates
  - [x] 4.1 Add passenger and luggage inputs to TripForm
    - Add a "Passengers & Luggage" row with number inputs for Passenger Count (default 1, range 1-9), Carry-On Bags (default 1, range 0-2), Checked Bags (default 0, range 0-5)
    - Add inline validation errors for out-of-range values
    - Include new fields in the GraphQL mutation input
    - Pre-populate fields when editing an existing trip
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.7_

  - [x] 4.2 Update GraphQL queries to include new fields
    - Add `passengerCount`, `carryOnBags`, `checkedBags` to `GET_TRIP_DETAIL` and `GET_TRIPS` queries
    - Add `totalPriceCents` to `topFlightOptions` in `GET_TRIP_DETAIL`
    - Add `totalCombinedPriceCents` to `roundTripOptions` in `GET_TRIP_DETAIL`
    - _Requirements: 6.5, 6.6, 6.7_

  - [x] 4.3 Update FlightOptions display to show total prices
    - Replace `priceCents` with `totalPriceCents` as the primary price column
    - Show per-passenger annotation when passenger_count > 1 or bag fees > 0
    - When passenger_count is 1 and bag fees are 0, show only base fare (no annotation)
    - Update round-trip table to use `totalCombinedPriceCents`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.4_

## Notes

- All prices are in cents (integer arithmetic) to avoid floating-point issues
- Unknown airline codes gracefully fall back to 0 bag fees
- Existing trip contracts remain unchanged due to column defaults matching current behavior

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "2.2"] },
    { "id": 2, "tasks": ["3.1", "3.2"] },
    { "id": 3, "tasks": ["4.1", "4.2"] },
    { "id": 4, "tasks": ["4.3"] }
  ]
}
```
