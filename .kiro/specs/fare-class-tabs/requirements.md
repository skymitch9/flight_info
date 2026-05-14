# Requirements Document

## Introduction

The FlightOptions component currently displays all fare classes (Economy, Premium Economy, Business, First) mixed together in a single table view. Users cannot easily compare pricing within a specific fare class. This feature adds a tabbed interface to the FlightOptions component so users can filter and view flight options by fare class independently. The backend already provides `fare_class` data on each price snapshot and flight option — this feature is purely a frontend presentation change.

## Glossary

- **Fare_Class_Tabs**: A horizontal tab bar UI element that allows users to switch between fare class views
- **FlightOptions_Component**: The React component responsible for rendering the one-way flight options table and round-trip combinations section
- **Fare_Class**: The cabin class of a flight option (Economy, Premium Economy, Business, First)
- **Active_Tab**: The currently selected fare class tab that determines which flight options are displayed
- **Flight_Options_Table**: The table displaying one-way flight options (date, airline, flight number, departure, arrival, stops, duration, price)
- **Round_Trip_Section**: The section below the flight options table that displays paired outbound and return flight combinations

## Requirements

### Requirement 1: Fare Class Tab Bar Display

**User Story:** As a user, I want to see a tab bar above the flight options table, so that I can switch between different fare classes.

#### Acceptance Criteria

1. THE Fare_Class_Tabs SHALL display tabs in the following left-to-right order: Economy, Premium Economy, Business, and First
2. THE Fare_Class_Tabs SHALL be rendered above the Flight_Options_Table within the FlightOptions_Component
3. THE Fare_Class_Tabs SHALL visually differentiate the Active_Tab from inactive tabs by applying a distinct background color or bottom border that contrasts with the inactive tab styling
4. THE Fare_Class_Tabs SHALL default to the Economy tab as the Active_Tab on initial render
5. WHEN the user clicks an inactive tab, THE Fare_Class_Tabs SHALL set that tab as the Active_Tab and THE Flight_Options_Table SHALL display only flight options matching the selected fare class
6. IF no flight options exist for the selected fare class, THEN THE Flight_Options_Table SHALL display a message indicating that no flights are available for that fare class

### Requirement 2: Tab Selection and Filtering

**User Story:** As a user, I want to click a fare class tab to see only flights of that fare class, so that I can compare pricing within a single cabin class.

#### Acceptance Criteria

1. WHEN a user clicks a fare class tab, THE FlightOptions_Component SHALL update the Active_Tab to the selected fare class immediately without a page reload
2. WHEN the Active_Tab changes, THE Flight_Options_Table SHALL display only flight options whose Fare_Class matches the Active_Tab value
3. WHEN the Active_Tab changes, THE Round_Trip_Section SHALL display only round-trip combinations where both the outbound and return flights have a Fare_Class matching the Active_Tab value
4. WHEN the Active_Tab is selected, THE FlightOptions_Component SHALL filter both one-way options and round-trip combinations using case-insensitive matching against the fare class field
5. WHEN the user clicks the already-active tab, THE FlightOptions_Component SHALL produce no change to the displayed data

### Requirement 3: Empty State Handling

**User Story:** As a user, I want to see a clear message when no flights are available for a selected fare class, so that I understand the data is filtered rather than missing.

#### Acceptance Criteria

1. WHEN the Active_Tab is selected and no flight options match the selected Fare_Class, THE Flight_Options_Table SHALL display an empty-state message that includes the name of the selected fare class, indicating that no one-way flights are available for that fare class
2. WHEN the Active_Tab is selected and no round-trip combinations match the selected Fare_Class, THE Round_Trip_Section SHALL remain visible and display an empty-state message that includes the name of the selected fare class, indicating that no round-trip options are available for that fare class
3. THE FlightOptions_Component SHALL display different message text for the one-way table empty state and the round-trip section empty state, each identifying the specific section (one-way or round-trip) that lacks data
4. WHEN the Active_Tab is selected and no flight options match the selected Fare_Class, THE Flight_Options_Table SHALL display the empty-state message in place of the table rows, without rendering the table header

### Requirement 4: Tab Badge Counts

**User Story:** As a user, I want to see how many flight options exist for each fare class, so that I can quickly identify which tabs have data.

#### Acceptance Criteria

1. THE Fare_Class_Tabs SHALL display a count badge to the right of each tab label showing the number of one-way flight options available for that fare class from the currently loaded data set
2. WHEN the flight options data changes, THE Fare_Class_Tabs SHALL update all count badges within the same render cycle to reflect the current data
3. IF a fare class has zero flight options, THEN THE Fare_Class_Tabs SHALL display "0" as the count badge and the tab SHALL remain clickable
4. THE Fare_Class_Tabs SHALL count flight options using case-insensitive matching against the fare class field, consistent with the tab filtering logic
5. IF the count for a fare class exceeds 999, THEN THE Fare_Class_Tabs SHALL display "999+" as the badge text

### Requirement 5: Visual Consistency

**User Story:** As a user, I want the fare class tabs to match the existing application styling, so that the interface feels cohesive.

#### Acceptance Criteria

1. THE Fare_Class_Tabs SHALL use the application's existing font families: Orbitron for tab labels, Share Tech Mono for count badges
2. THE Fare_Class_Tabs SHALL use cyan (#00F0FF) for the Active_Tab text and border, and #555577 for inactive tab text
3. THE Fare_Class_Tabs SHALL remain on a single horizontal line when viewport width is 1024px or greater
4. WHEN viewport width is below 1024px, THE Fare_Class_Tabs SHALL allow horizontal scrolling rather than wrapping to multiple lines
5. THE Fare_Class_Tabs SHALL use inline styles consistent with the existing FlightOptions component styling patterns
