# Implementation Plan: Fare Class Tabs

## Overview

Add a tabbed interface to the `FlightOptions` component in `frontend/src/components/FlightOptions.tsx` that allows users to filter flights by fare class (Economy, Premium Economy, Business, First). The implementation is entirely frontend — a new internal `FareClassTabs` sub-component, filtering logic, state management, and empty-state handling all within the existing file.

## Tasks

- [x] 1. Add fare class constants and filtering utility functions
  - [x] 1.1 Add the FARE_CLASS_ORDER constant and pure filtering/counting functions
    - Add `FARE_CLASS_ORDER` constant array: `['Economy', 'Premium Economy', 'Business', 'First']`
    - Add `filterByFareClass(options, fareClass)` function that filters one-way options by case-insensitive fare class match
    - Add `filterRoundTripsByFareClass(roundTrips, fareClass)` function that filters round-trip options where both outbound and return match the fare class (case-insensitive)
    - Add `countByFareClass(options)` function that returns a Record of counts per fare class
    - Add `formatBadgeCount(count)` function that returns "999+" for counts exceeding 999
    - _Requirements: 2.2, 2.3, 2.4, 4.1, 4.4, 4.5_

- [x] 2. Implement the FareClassTabs sub-component
  - [x] 2.1 Create the FareClassTabs internal component with tab bar rendering
    - Define `FareClassTabsProps` interface with `activeTab`, `onTabChange`, and `counts` props
    - Render a horizontal tab bar with tabs in order: Economy, Premium Economy, Business, First
    - Display count badge to the right of each tab label using `formatBadgeCount`
    - Style active tab with cyan (#00F0FF) text and bottom border; inactive tabs with #555577
    - Use Orbitron font for tab labels, Share Tech Mono for badge counts
    - Ensure single-line layout at viewport ≥1024px with horizontal scroll below 1024px
    - Use inline styles consistent with existing component patterns
    - _Requirements: 1.1, 1.2, 1.3, 4.1, 4.3, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 3. Integrate tab state and filtering into FlightOptions component
  - [x] 3.1 Add activeTab state and memoized filtered data to FlightOptions
    - Add `useState` for `activeTab` defaulting to `"Economy"`
    - Add `useMemo` for `counts` derived from `countByFareClass(options)`
    - Add `useMemo` for `filteredOptions` derived from `filterByFareClass(options, activeTab)`
    - Add `useMemo` for `filteredRoundTrips` derived from `filterRoundTripsByFareClass(roundTripOptions, activeTab)`
    - Import `useMemo` from React
    - _Requirements: 1.4, 2.1, 2.4, 4.2_

  - [x] 3.2 Render FareClassTabs and wire up filtered data
    - Render `FareClassTabs` above the flight options table, passing `activeTab`, `onTabChange`, and `counts`
    - Ensure clicking an inactive tab updates `activeTab`; clicking the active tab does nothing
    - Replace `options` with `filteredOptions` in the one-way table tbody rendering
    - Replace `roundTripOptions` with `filteredRoundTrips` in the round-trip section rendering
    - _Requirements: 1.2, 1.5, 2.1, 2.5_

- [x] 4. Implement empty state handling
  - [x] 4.1 Add empty-state messages for filtered views
    - When `filteredOptions` is empty, display an empty-state message including the active fare class name instead of the table header and rows (e.g., "No Economy flights available")
    - When `filteredRoundTrips` is empty, display a distinct empty-state message in the round-trip section including the fare class name (e.g., "No Economy round-trip combinations available")
    - Use different message text for one-way vs round-trip empty states
    - Style empty-state messages using existing `noData` style patterns
    - _Requirements: 1.6, 3.1, 3.2, 3.3, 3.4_

## Notes

- All changes are in a single file: `frontend/src/components/FlightOptions.tsx`
- No new dependencies required — uses React's built-in `useState` and `useMemo`
- The `FareClassTabs` component is defined internally in the same file, consistent with existing patterns (`SegmentDetail`, `FlightRow`)
- Filtering is case-insensitive to handle any casing variations in the `fareClass` field
- Each task references specific requirements for traceability

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "3.1"] },
    { "id": 2, "tasks": ["3.2"] },
    { "id": 3, "tasks": ["4.1"] }
  ]
}
```
