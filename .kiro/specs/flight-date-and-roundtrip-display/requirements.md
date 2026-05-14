# Requirements Document

## Introduction

This feature enhances the "Available Flights" section in the trip detail view by adding flight date visibility and round-trip combination options. Currently, the FlightOptions component displays one-way outbound flight options sorted by price but does not show which date each flight departs on. Since contracts use date ranges (earliest_departure to latest_departure), flights are collected across multiple dates and users need to see which specific date each option is for. Additionally, users want to see round-trip combinations that pair outbound and return flights with a combined total price.

## Glossary

- **Flight_Options_Display**: The UI component that renders available flight options in the trip detail view
- **Price_Snapshot**: A collected data point representing a specific flight's price, airline, times, and date
- **Trip_Contract**: A user-defined trip request with date ranges for departure and optional return
- **Outbound_Flight**: A one-way flight from origin to destination within the departure date range
- **Return_Flight**: A one-way flight from destination back to origin within the return date range
- **Round_Trip_Option**: A paired combination of one outbound flight and one return flight with a combined total price
- **Flight_Date**: The specific calendar date on which a flight departs (stored as flight_date on Price_Snapshot)
- **GraphQL_API**: The Strawberry GraphQL backend that resolves flight option data for the frontend

## Requirements

### Requirement 1: Display Flight Date on One-Way Options

**User Story:** As a user, I want to see the departure date for each flight option, so that I know which specific day the flight leaves within my date range.

#### Acceptance Criteria

1. THE GraphQL_API SHALL include a flight_date field on the FlightOptionType representing the calendar date of departure
2. WHEN the Flight_Options_Display renders a one-way flight option, THE Flight_Options_Display SHALL show the flight_date in a human-readable format alongside the existing flight details
3. THE Flight_Options_Display SHALL group or visually distinguish flight options by their flight_date so users can compare options across different dates

### Requirement 2: Provide Round-Trip Flight Combinations

**User Story:** As a user, I want to see round-trip flight combinations pairing outbound and return flights, so that I can evaluate total trip cost without manually adding prices.

#### Acceptance Criteria

1. WHEN a Trip_Contract has both departure and return date ranges defined, THE GraphQL_API SHALL return round-trip flight combinations in addition to one-way options
2. THE GraphQL_API SHALL construct each Round_Trip_Option by pairing one Outbound_Flight with one Return_Flight
3. THE GraphQL_API SHALL calculate the combined price of a Round_Trip_Option as the sum of the outbound flight price_cents and the return flight price_cents
4. THE GraphQL_API SHALL sort Round_Trip_Options by combined price in ascending order
5. THE GraphQL_API SHALL return up to 10 Round_Trip_Options

### Requirement 3: Display Round-Trip Options in the UI

**User Story:** As a user, I want to view round-trip combinations in the flight options section, so that I can quickly identify the cheapest complete trip.

#### Acceptance Criteria

1. WHEN round-trip options are available, THE Flight_Options_Display SHALL render a separate section for round-trip combinations distinct from the one-way options section
2. THE Flight_Options_Display SHALL show the outbound flight date, outbound flight details, return flight date, and return flight details for each Round_Trip_Option
3. THE Flight_Options_Display SHALL show the combined total price for each Round_Trip_Option
4. WHEN a Trip_Contract has no return date range defined, THE Flight_Options_Display SHALL show only the one-way options section without a round-trip section

### Requirement 4: Round-Trip Pairing Logic

**User Story:** As a user, I want round-trip pairings to respect my contract date constraints, so that only valid combinations within my specified ranges are shown.

#### Acceptance Criteria

1. THE GraphQL_API SHALL only pair Outbound_Flights with flight_date within the Trip_Contract earliest_departure to latest_departure range
2. THE GraphQL_API SHALL only pair Return_Flights with flight_date within the Trip_Contract earliest_return to latest_return range
3. THE GraphQL_API SHALL only create Round_Trip_Options where the return flight_date is on or after the outbound flight_date
4. WHEN applying the latest_return_time constraint, THE GraphQL_API SHALL exclude Return_Flights with arrival_time later than the specified latest_return_time

### Requirement 5: One-Way Options Retain Date Filtering

**User Story:** As a user, I want one-way outbound options to continue respecting my departure time constraints while now also showing dates, so that the existing filtering behavior is preserved.

#### Acceptance Criteria

1. WHEN the Trip_Contract has a latest_departure_time set, THE GraphQL_API SHALL exclude Outbound_Flights with arrival_time later than the latest_departure_time from one-way options
2. THE GraphQL_API SHALL continue to sort one-way options by price_cents in ascending order
3. THE GraphQL_API SHALL continue to return up to 10 one-way Outbound_Flight options
