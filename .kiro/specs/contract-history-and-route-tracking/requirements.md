# Requirements Document

## Introduction

This feature introduces a contract history/archive system and route-level tracking to the Flight Deal Tracker. When a trip contract is fulfilled (ticket purchased), it moves to a history section while its route continues to be tracked for price data. Routes are deduplicated so that multiple contracts sharing the same origin-destination pair share a single data collection run, reducing redundant API calls and preserving long-term price intelligence.

## Glossary

- **Contract**: A TripRequest representing a user's intent to purchase a flight on a specific route within a date range. Synonymous with "trip request."
- **Route**: A unique origin-destination airport pair (e.g., PHX→ATL) tracked independently of individual contracts.
- **Route_Tracker**: The subsystem responsible for managing route-level data collection and deduplication.
- **Contract_Archive**: The subsystem responsible for moving fulfilled contracts to history and preserving their associated data.
- **Collection_Service**: The existing service that fetches flight prices from external APIs (SerpAPI, Amadeus).
- **Price_Snapshot**: A recorded price data point for a flight on a given date.
- **Fulfillment**: The event when a user marks a contract as purchased/completed.

## Requirements

### Requirement 1: Route Entity and Deduplication

**User Story:** As a user, I want routes to be tracked independently from my individual contracts, so that the system avoids redundant API calls when multiple contracts share the same route.

#### Acceptance Criteria

1. THE Route_Tracker SHALL maintain a unique Route record for each distinct origin-destination airport pair.
2. WHEN a new contract is created, THE Route_Tracker SHALL associate the contract with an existing Route if one matches the origin-destination pair.
3. WHEN a new contract is created and no matching Route exists, THE Route_Tracker SHALL create a new Route record for that origin-destination pair.
4. WHILE multiple active contracts reference the same Route, THE Collection_Service SHALL execute only one data collection run per Route per collection cycle.
5. THE Route_Tracker SHALL store Price_Snapshots at the Route level rather than the individual contract level.

### Requirement 2: Contract Fulfillment and Archival

**User Story:** As a user, I want to mark a contract as fulfilled when I purchase a ticket, so that it moves to a history section and no longer appears in my active contracts list.

#### Acceptance Criteria

1. WHEN a user marks a contract as fulfilled, THE Contract_Archive SHALL set the contract status to "fulfilled" and record the fulfillment timestamp.
2. WHEN a contract is fulfilled, THE Contract_Archive SHALL preserve all associated price history and analysis results linked to that contract.
3. WHEN a contract is fulfilled, THE Contract_Archive SHALL remove the contract from the active contracts view.
4. THE Contract_Archive SHALL allow a user to view fulfilled contracts in a dedicated history section.
5. IF the last active contract referencing a Route is fulfilled, THEN THE Route_Tracker SHALL continue collecting price data for that Route.

### Requirement 3: Route-Level Persistent Tracking

**User Story:** As a user, I want price data to keep being collected for routes even after all my contracts on that route are fulfilled, so that I have long-term price intelligence for future trips.

#### Acceptance Criteria

1. THE Route_Tracker SHALL continue scheduled price collection for a Route regardless of whether active contracts reference that Route.
2. WHEN a Route has no active contracts and no price data has been collected in the last 90 days, THE Route_Tracker SHALL mark the Route as dormant.
3. WHILE a Route is dormant, THE Collection_Service SHALL skip data collection for that Route.
4. WHEN a new contract is created referencing a dormant Route, THE Route_Tracker SHALL reactivate the Route for collection.

### Requirement 4: Contract History View

**User Story:** As a user, I want to browse my fulfilled contracts and see their historical price data, so that I can review past trip decisions and price trends.

#### Acceptance Criteria

1. THE Contract_Archive SHALL provide a list of all fulfilled contracts with their origin, destination, date ranges, and fulfillment date.
2. WHEN a user selects a fulfilled contract from history, THE Contract_Archive SHALL display the price snapshots and analysis results that were associated with that contract at the time of fulfillment.
3. THE Contract_Archive SHALL display the final recommendation and explanation that was active when the contract was fulfilled.

### Requirement 5: Route Price History Access

**User Story:** As a user, I want to view the full price history for a route across all time, so that I can understand long-term pricing patterns independent of any single contract.

#### Acceptance Criteria

1. THE Route_Tracker SHALL provide access to all Price_Snapshots collected for a Route, spanning all contracts past and present.
2. WHEN a user views a Route's price history, THE Route_Tracker SHALL display data points with their collection timestamps and flight details.
3. THE Route_Tracker SHALL indicate which contracts were active during each price collection period.

### Requirement 6: Collection Service Route-Level Integration

**User Story:** As a developer, I want the collection service to operate at the route level, so that API calls are deduplicated and price data is shared across contracts.

#### Acceptance Criteria

1. WHEN a collection cycle runs, THE Collection_Service SHALL query distinct active Routes rather than individual contracts.
2. WHEN prices are collected for a Route, THE Collection_Service SHALL store snapshots linked to the Route record.
3. WHEN prices are collected for a Route, THE Collection_Service SHALL make the data available to all contracts referencing that Route for analysis purposes.
4. IF a Route collection fails, THEN THE Collection_Service SHALL log the error and continue with remaining Routes.

### Requirement 7: New Trip Contracts (PHX→ATL and PHX→KIX)

**User Story:** As a user, I want to create specific trip contracts for PHX→ATL (fixed dates, September 3-10) and PHX→KIX (flexible dates, September-November), so that the system begins tracking prices for these routes.

#### Acceptance Criteria

1. WHEN the PHX→ATL contract is created, THE Route_Tracker SHALL record a departure date of September 3 with a morning departure constraint and a return date of September 10 with an afternoon arrival constraint (Arizona time).
2. WHEN the PHX→KIX contract is created, THE Route_Tracker SHALL record flexible departure dates spanning September through November of the next year.
3. WHEN either contract is created, THE Route_Tracker SHALL create or reuse the corresponding Route record for deduplication.

### Requirement 8: Data Migration for Existing Contracts

**User Story:** As a developer, I want existing price snapshots to be migrated to the new route-level structure, so that historical data is preserved and the system transitions cleanly.

#### Acceptance Criteria

1. WHEN the migration runs, THE Route_Tracker SHALL create Route records for each distinct origin-destination pair found in existing contracts.
2. WHEN the migration runs, THE Route_Tracker SHALL re-link existing Price_Snapshots from individual contracts to their corresponding Route records.
3. WHEN the migration runs, THE Route_Tracker SHALL preserve all existing contract-to-snapshot associations for historical reference.
4. IF the migration encounters a Price_Snapshot with no matching Route, THEN THE Route_Tracker SHALL create the Route and link the snapshot.
