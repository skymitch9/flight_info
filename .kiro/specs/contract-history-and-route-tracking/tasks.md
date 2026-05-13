# Implementation Plan: Contract History and Route Tracking

## Overview

Introduce a Route entity that owns price collection, refactor the collection service to iterate routes instead of individual contracts, add contract fulfillment lifecycle (active → fulfilled), and build frontend views for contract history and route-level price data. A migration script transitions existing data to the new structure.

## Tasks

- [ ] 1. Create Route model and update existing models
  - [ ] 1.1 Add Route SQLAlchemy model to `app/models.py`
    - Create `Route` class with columns: id, origin, destination, status (default "active"), last_collected_at, created_at
    - Add `UniqueConstraint("origin", "destination", name="uq_route_origin_dest")`
    - Add `price_snapshots` and `trip_requests` relationships
    - _Requirements: 1.1_

  - [ ] 1.2 Modify TripRequest model with route_id, status, fulfilled_at
    - Add `route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)` (nullable during migration, enforced after)
    - Add `status = Column(String(10), nullable=False, default="active")`
    - Add `fulfilled_at = Column(DateTime, nullable=True)`
    - Add `route = relationship("Route", back_populates="trip_requests")`
    - _Requirements: 2.1, 1.2_

  - [ ] 1.3 Modify PriceSnapshot model with route_id, make trip_request_id nullable
    - Add `route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)` (nullable during migration)
    - Change `trip_request_id` to `nullable=True`
    - Add `route = relationship("Route", back_populates="price_snapshots")`
    - _Requirements: 1.5, 6.2_

- [ ] 2. Implement RouteTracker service
  - [ ] 2.1 Create `app/route_tracker/__init__.py` and `app/route_tracker/service.py`
    - Implement `get_or_create_route(session, origin, destination)` — SELECT existing or INSERT new Route
    - Implement `get_active_routes(session)` — return routes where status == "active"
    - Implement `mark_dormant(session, route_id)` — set status to "dormant"
    - Implement `reactivate_route(session, route_id)` — set status to "active"
    - Implement `check_dormancy(session)` — find routes with no active contracts and last_collected_at > 90 days ago, mark dormant
    - Handle unique constraint race condition with retry logic
    - _Requirements: 1.2, 1.3, 3.1, 3.2, 3.3, 3.4_

  - [ ]* 2.2 Write property test: Route Uniqueness Invariant
    - **Property 1: Route Uniqueness Invariant**
    - **Validates: Requirements 1.1**

  - [ ]* 2.3 Write property test: get_or_create Route Idempotence
    - **Property 2: get_or_create Route Idempotence**
    - **Validates: Requirements 1.2, 1.3, 7.3**

  - [ ]* 2.4 Write property test: Dormancy Lifecycle Round-Trip
    - **Property 9: Dormancy Lifecycle Round-Trip**
    - **Validates: Requirements 3.2, 3.3, 3.4**

- [ ] 3. Modify TripManager for fulfillment and route linking
  - [ ] 3.1 Update `app/trip_manager/service.py` — integrate route linking on trip creation
    - In `create_trip()`, call `RouteTracker.get_or_create_route(origin, destination)` and set `route_id` on the new TripRequest
    - If the route was dormant, call `reactivate_route()`
    - _Requirements: 1.2, 1.3, 3.4_

  - [ ] 3.2 Add `fulfill_trip(trip_id)` method to TripService
    - Validate trip exists and status is "active" (error if already fulfilled)
    - Set `status = "fulfilled"` and `fulfilled_at = datetime.utcnow()`
    - _Requirements: 2.1_

  - [ ] 3.3 Add `list_fulfilled_trips()` method to TripService
    - Query TripRequests where `status == "fulfilled"`, load relationships
    - _Requirements: 2.4, 4.1_

  - [ ]* 3.4 Write property test: Fulfillment Sets Status and Timestamp
    - **Property 5: Fulfillment Sets Status and Timestamp**
    - **Validates: Requirements 2.1**

  - [ ]* 3.5 Write property test: Fulfillment Preserves Historical Data
    - **Property 6: Fulfillment Preserves Historical Data**
    - **Validates: Requirements 2.2**

  - [ ]* 3.6 Write property test: Contract List Partitioning by Status
    - **Property 7: Contract List Partitioning by Status**
    - **Validates: Requirements 2.3, 2.4, 4.1**

  - [ ]* 3.7 Write property test: Route Persists After Last Contract Fulfilled
    - **Property 8: Route Persists After Last Contract Fulfilled**
    - **Validates: Requirements 2.5, 3.1**

- [ ] 4. Refactor CollectionService to route-level iteration
  - [ ] 4.1 Modify `app/collector/service.py` to iterate routes
    - Replace `_get_active_trips()` with call to `RouteTracker.get_active_routes()`
    - Refactor `collect_all()` to iterate routes, collect prices per route
    - Update `_store_snapshots()` to accept `route_id` instead of `trip_request_id`
    - After storing snapshots, update `route.last_collected_at`
    - After collection per route, trigger analysis for each active contract on that route
    - _Requirements: 6.1, 6.2, 6.3, 1.4_

  - [ ]* 4.2 Write property test: Collection Deduplication
    - **Property 3: Collection Deduplication**
    - **Validates: Requirements 1.4, 6.1**

  - [ ]* 4.3 Write property test: Snapshots Stored at Route Level
    - **Property 4: Snapshots Stored at Route Level**
    - **Validates: Requirements 1.5, 6.2**

  - [ ]* 4.4 Write property test: Route Data Accessible to All Contracts
    - **Property 11: Route Data Accessible to All Contracts**
    - **Validates: Requirements 6.3**

  - [ ]* 4.5 Write property test: Collection Error Resilience
    - **Property 12: Collection Error Resilience**
    - **Validates: Requirements 6.4**

- [ ] 5. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Update GraphQL schema with new queries and mutations
  - [ ] 6.1 Add `RouteType` to GraphQL schema
    - Define `RouteType` with fields: id, origin, destination, status, lastCollectedAt, priceHistory, activeContracts
    - _Requirements: 5.1, 5.2_

  - [ ] 6.2 Add `fulfilledTrips` query
    - Return fulfilled contracts with origin, destination, date ranges, fulfillment date, final recommendation
    - _Requirements: 2.4, 4.1, 4.2, 4.3_

  - [ ] 6.3 Add `route(routeId: Int!)` and `routes` queries
    - `route` returns a single route with full price history
    - `routes` returns all tracked routes with status
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 6.4 Add `fulfillTrip(tripId: Int!)` mutation
    - Call `TripService.fulfill_trip()`, return updated TripRequestType
    - _Requirements: 2.1_

  - [ ] 6.5 Update existing `trips` query to filter by status "active"
    - Ensure only active contracts appear in the main trips list
    - _Requirements: 2.3_

- [ ] 7. Build frontend ContractHistory page and route views
  - [ ] 7.1 Add GraphQL queries and mutations to `frontend/src/graphql/queries.ts`
    - Add `GET_FULFILLED_TRIPS` query
    - Add `GET_ROUTE` and `GET_ROUTES` queries
    - Add `FULFILL_TRIP` mutation
    - _Requirements: 4.1, 5.1_

  - [ ] 7.2 Create `frontend/src/pages/ContractHistory.tsx`
    - List fulfilled contracts with origin, destination, date ranges, fulfillment date, final recommendation
    - Link each item to its detail view
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ] 7.3 Create `frontend/src/components/RoutePriceHistory.tsx`
    - Display all-time price data for a route with collection timestamps and flight details
    - Indicate which contracts were active during each collection period
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 7.4 Add "Mark as Fulfilled" button to TripDetail page
    - Add button that calls `FULFILL_TRIP` mutation
    - On success, redirect to contract history or show confirmation
    - _Requirements: 2.1_

  - [ ] 7.5 Add navigation to ContractHistory page in App routing
    - Add route in `App.tsx` for `/history`
    - Add navigation link in TripList header
    - _Requirements: 4.1_

- [ ] 8. Checkpoint - Ensure frontend builds and backend integration works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Create migration script for existing data
  - [ ] 9.1 Create `scripts/migrate_routes.py`
    - Create `routes` table if not exists
    - For each distinct (origin, destination) in trip_requests, insert a Route record
    - Update each TripRequest with the corresponding route_id
    - Update each PriceSnapshot with route_id derived from its trip_request's route_id
    - Set status = "active" where is_active = True, status = "fulfilled" where is_active = False
    - Make PriceSnapshot.trip_request_id nullable
    - Add NOT NULL constraint on route_id columns after population
    - Handle edge case: orphaned snapshots with no matching route
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 9.2 Write property test: Migration Data Integrity
    - **Property 13: Migration Data Integrity**
    - **Validates: Requirements 8.1, 8.2, 8.3**

- [ ] 10. Create new trip contracts (PHX→ATL and PHX→KIX)
  - [ ] 10.1 Add seed script or instructions to create PHX→ATL contract
    - Departure: September 3, morning departure constraint
    - Return: September 10, afternoon arrival constraint (Arizona time)
    - Ensure Route record is created/reused via RouteTracker
    - _Requirements: 7.1, 7.3_

  - [ ] 10.2 Add seed script or instructions to create PHX→KIX contract
    - Flexible departure dates spanning September through November of next year
    - Ensure Route record is created/reused via RouteTracker
    - _Requirements: 7.2, 7.3_

- [ ]* 10.3 Write property test: Route Price History Completeness
  - **Property 10: Route Price History Completeness**
  - **Validates: Requirements 5.1, 5.2**

- [ ] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend uses Python (SQLAlchemy, Strawberry GraphQL, Hypothesis for property tests)
- Frontend uses TypeScript (React, Apollo Client)
- Each property test references its design document property number
- Checkpoints ensure incremental validation between major phases
- Migration script should be idempotent (safe to re-run)
