# Implementation Plan: Flight Date and Round-Trip Display

## Overview

This plan implements flight date visibility on one-way options and introduces round-trip flight combinations in the GraphQL API and frontend. The backend changes are concentrated in `app/graphql_api/schema.py` (new types, pairing logic, resolver updates), while the frontend changes update the GraphQL query and `FlightOptions` component to display dates and a new round-trip section.

## Tasks

- [x] 1. Update GraphQL schema types and add flight_date to FlightOptionType
  - [x] 1.1 Add `flight_date` field to `FlightOptionType` and update `_derive_top_flight_options` to populate it
    - Add `flight_date: date` field to the `FlightOptionType` strawberry type in `app/graphql_api/schema.py`
    - Update the list comprehension in `_derive_top_flight_options` to include `flight_date=snap.flight_date`
    - Update `TripRequestType` to include `round_trip_options: list[RoundTripOptionType]` field (empty list default for now)
    - _Requirements: 1.1, 5.1, 5.2, 5.3_

  - [x] 1.2 Create `RoundTripOptionType` strawberry type
    - Define `RoundTripOptionType` with fields: `outbound: FlightOptionType`, `return_flight: FlightOptionType`, `combined_price_cents: int`
    - Place it in `app/graphql_api/schema.py` alongside existing types
    - _Requirements: 2.2, 2.3_

- [x] 2. Implement round-trip pairing logic
  - [x] 2.1 Implement `_get_latest_batch` helper function
    - Extract the latest-batch filtering logic (5-minute window) from `_derive_top_flight_options` into a reusable `_get_latest_batch(snapshots) -> list[PriceSnapshot]` function
    - Refactor `_derive_top_flight_options` to use `_get_latest_batch`
    - _Requirements: 2.1_

  - [x] 2.2 Implement `_derive_round_trip_options` function
    - Create `_derive_round_trip_options(outbound_snapshots, return_snapshots, trip) -> list[RoundTripOptionType]`
    - Filter outbound snapshots to latest batch using `_get_latest_batch`
    - Filter return snapshots to latest batch using `_get_latest_batch`
    - Filter outbound flights: `flight_date` within `earliest_departure` to `latest_departure`; if `latest_departure_time` set, exclude flights with `arrival_time` > constraint
    - Filter return flights: `flight_date` within `earliest_return` to `latest_return`; if `latest_return_time` set, exclude flights with `arrival_time` > constraint
    - Form cartesian product of valid outbound × return snapshots
    - Filter pairs where `return.flight_date >= outbound.flight_date`
    - Calculate `combined_price_cents = outbound.price_cents + return.price_cents`
    - Sort by `combined_price_cents` ascending, take top 10
    - Map to `RoundTripOptionType` objects
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.2, 4.3, 4.4_

- [x] 3. Update resolvers to fetch return snapshots and wire round-trip options
  - [x] 3.1 Update `_map_trip_to_type` to accept return snapshots and populate `round_trip_options`
    - Add `return_snapshots: list[PriceSnapshot] = []` parameter to `_map_trip_to_type`
    - Call `_derive_round_trip_options(trip.price_snapshots, return_snapshots, trip)` when trip has return dates
    - Pass empty list for `round_trip_options` when trip has no return dates
    - _Requirements: 2.1, 3.4_

  - [x] 3.2 Update query resolvers to look up reverse route and load return snapshots
    - In the `trip` resolver: query for reverse `Route` where `origin=trip.destination, destination=trip.origin`
    - Load the reverse route's `price_snapshots` via selectinload
    - Pass return snapshots to `_map_trip_to_type`
    - In the `trips` resolver: batch-query reverse routes for all trips with return dates
    - Handle case where reverse route does not exist (pass empty list)
    - _Requirements: 2.1, 4.1, 4.2_

- [x] 4. Update frontend GraphQL query and FlightOptions component
  - [x] 4.1 Update `GET_TRIP_DETAIL` query to include `flightDate` and `roundTripOptions`
    - Add `flightDate` field to `topFlightOptions` selection in `frontend/src/graphql/queries.ts`
    - Add `roundTripOptions` field with sub-selections: `outbound { ... }`, `returnFlight { ... }`, `combinedPriceCents`
    - _Requirements: 1.1, 2.1, 3.1_

  - [x] 4.2 Update `FlightOptions` component to display flight date on one-way options
    - Add `flightDate` to the `FlightOption` interface
    - Add a DATE column to the table header
    - Display the formatted flight date in each row
    - Group or visually distinguish options by date (e.g., date separator rows or date badge)
    - _Requirements: 1.2, 1.3_

  - [x] 4.3 Create round-trip options section in `FlightOptions` component
    - Add `RoundTripOption` interface with `outbound`, `returnFlight`, and `combinedPriceCents`
    - Add `roundTripOptions` prop to the component (or create a sibling `RoundTripOptions` section)
    - Render a separate "Round-Trip Combinations" section when `roundTripOptions` is non-empty
    - Display outbound date, outbound details, return date, return details, and combined price for each option
    - Hide the round-trip section entirely when no round-trip options are available
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 4.4 Update `TripDetail` page to pass round-trip data to `FlightOptions`
    - Update the `TripDetail` page component to extract `roundTripOptions` from the query response
    - Pass both `topFlightOptions` and `roundTripOptions` to the display component
    - _Requirements: 3.1_

## Notes

- Each task references specific requirements for traceability
- No database schema changes are needed — `PriceSnapshot.flight_date` already exists
- The backend pairing logic is a pure function

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "3.1"] },
    { "id": 3, "tasks": ["3.2"] },
    { "id": 4, "tasks": ["4.1"] },
    { "id": 5, "tasks": ["4.2", "4.3"] },
    { "id": 6, "tasks": ["4.4"] }
  ]
}
```
