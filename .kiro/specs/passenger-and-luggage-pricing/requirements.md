# Requirements Document

## Introduction

This feature extends trip contracts (TripRequest) to include passenger count and luggage requirements. The system will use these inputs to calculate a total trip cost that reflects the real expense for the entire travel party, including per-passenger bag fees that vary by airline. Currently, the app only displays per-seat base fares. After this feature, users will see an all-in price: (base_fare + bag_fees) × number_of_passengers.

## Glossary

- **Trip_Contract**: A user-defined trip request (TripRequest model) that tracks flight prices for a specific route and date range.
- **Passenger_Count**: The number of travelers in the party for a given Trip_Contract.
- **Carry_On_Bags**: The number of carry-on bags per passenger that the user intends to bring.
- **Checked_Bags**: The number of checked bags per passenger that the user intends to bring.
- **Bag_Fee_Schedule**: A data store of airline-specific luggage fees, keyed by airline code and bag type.
- **Base_Fare**: The per-seat ticket price for a flight option, excluding ancillary fees.
- **Total_Price**: The all-in cost calculated as (Base_Fare + applicable bag fees per passenger) × Passenger_Count.
- **Price_Calculator**: The backend component responsible for computing Total_Price from Base_Fare, Bag_Fee_Schedule, and luggage inputs.
- **Trip_Form**: The frontend component where users create or edit Trip_Contracts.
- **Flight_Options_Display**: The frontend component that renders available flights and their prices.

## Requirements

### Requirement 1: Passenger Count on Trip Contract

**User Story:** As a traveler, I want to specify how many passengers are in my party when creating a trip contract, so that the system can calculate the total cost for everyone.

#### Acceptance Criteria

1. WHEN a user creates a Trip_Contract, THE Trip_Form SHALL display a Passenger_Count input field with a default value of 1.
2. THE Trip_Form SHALL accept a Passenger_Count value between 1 and 9 inclusive.
3. IF the user enters a Passenger_Count less than 1 or greater than 9, THEN THE Trip_Form SHALL display a validation error and prevent submission.
4. WHEN a Trip_Contract is saved, THE System SHALL persist the Passenger_Count value in the database.
5. WHEN a user edits an existing Trip_Contract, THE Trip_Form SHALL pre-populate the Passenger_Count field with the stored value.

### Requirement 2: Luggage Requirements on Trip Contract

**User Story:** As a traveler, I want to specify how many carry-on and checked bags I need per passenger, so that bag fees are factored into the price.

#### Acceptance Criteria

1. WHEN a user creates a Trip_Contract, THE Trip_Form SHALL display input fields for Carry_On_Bags and Checked_Bags per passenger.
2. THE Trip_Form SHALL default Carry_On_Bags to 1 and Checked_Bags to 0.
3. THE Trip_Form SHALL accept Carry_On_Bags values between 0 and 2 inclusive.
4. THE Trip_Form SHALL accept Checked_Bags values between 0 and 5 inclusive.
5. IF the user enters luggage values outside the allowed range, THEN THE Trip_Form SHALL display a validation error and prevent submission.
6. WHEN a Trip_Contract is saved, THE System SHALL persist the Carry_On_Bags and Checked_Bags values in the database.
7. WHEN a user edits an existing Trip_Contract, THE Trip_Form SHALL pre-populate the luggage fields with the stored values.

### Requirement 3: Airline Bag Fee Schedule

**User Story:** As a system operator, I want to maintain a schedule of airline bag fees, so that the system can accurately estimate luggage costs per airline.

#### Acceptance Criteria

1. THE System SHALL store a Bag_Fee_Schedule containing per-bag fees for each supported airline code.
2. THE Bag_Fee_Schedule SHALL include separate fee entries for carry-on bags and checked bags.
3. THE Bag_Fee_Schedule SHALL support different fees for the first and second checked bag per passenger.
4. WHEN an airline includes carry-on bags at no extra charge, THE Bag_Fee_Schedule SHALL record a fee of 0 cents for that airline's carry-on entry.
5. IF a flight's airline code has no entry in the Bag_Fee_Schedule, THEN THE Price_Calculator SHALL use a fee of 0 cents for all bag types for that airline.

### Requirement 4: Total Price Calculation

**User Story:** As a traveler, I want to see the total trip cost including bag fees for all passengers, so that I can compare the true cost of different flight options.

#### Acceptance Criteria

1. WHEN flight options are displayed, THE Price_Calculator SHALL compute Total_Price as (Base_Fare + bag_fees_per_passenger) × Passenger_Count.
2. THE Price_Calculator SHALL determine bag_fees_per_passenger by summing the applicable carry-on fee and checked bag fees from the Bag_Fee_Schedule for the flight's airline.
3. WHEN a flight option has multiple segments with different airlines, THE Price_Calculator SHALL apply the bag fee from the operating airline of the first segment.
4. THE Price_Calculator SHALL compute bag fees using the Carry_On_Bags and Checked_Bags values stored on the Trip_Contract.
5. FOR ALL valid combinations of Base_Fare, Passenger_Count, and luggage values, computing Total_Price then dividing by Passenger_Count and subtracting bag_fees_per_passenger SHALL yield the original Base_Fare (round-trip property).

### Requirement 5: Updated Price Display

**User Story:** As a traveler, I want the flight options view to show both the per-person price and the total party price, so that I can quickly assess the full cost.

#### Acceptance Criteria

1. WHEN flight options are rendered, THE Flight_Options_Display SHALL show the Total_Price as the primary price column.
2. THE Flight_Options_Display SHALL show the per-passenger price (Base_Fare + bag_fees_per_passenger) as a secondary annotation below the Total_Price.
3. WHEN Passenger_Count is 1 and bag fees are 0, THE Flight_Options_Display SHALL show only the Base_Fare without a secondary annotation.
4. WHEN round-trip combinations are displayed, THE Flight_Options_Display SHALL compute the combined Total_Price as the sum of outbound Total_Price and return Total_Price.
5. THE Flight_Options_Display SHALL format all prices in US dollars with no decimal places, consistent with the existing format.

### Requirement 6: GraphQL API Extension

**User Story:** As a frontend developer, I want the GraphQL API to expose passenger and luggage fields, so that the frontend can send and receive this data.

#### Acceptance Criteria

1. THE TripRequestInput GraphQL type SHALL include optional fields for passenger_count, carry_on_bags, and checked_bags.
2. WHEN passenger_count is not provided in the input, THE System SHALL default the value to 1.
3. WHEN carry_on_bags is not provided in the input, THE System SHALL default the value to 1.
4. WHEN checked_bags is not provided in the input, THE System SHALL default the value to 0.
5. THE TripRequestType GraphQL type SHALL expose passenger_count, carry_on_bags, and checked_bags fields.
6. THE FlightOptionType GraphQL type SHALL expose a total_price_cents field representing the computed Total_Price.
7. THE RoundTripOptionType GraphQL type SHALL expose a total_combined_price_cents field representing the sum of outbound and return Total_Price values.

### Requirement 7: Backward Compatibility

**User Story:** As an existing user, I want my current trip contracts to continue working without modification after this update.

#### Acceptance Criteria

1. WHEN the database migration runs, THE System SHALL set Passenger_Count to 1 for all existing Trip_Contracts.
2. WHEN the database migration runs, THE System SHALL set Carry_On_Bags to 1 for all existing Trip_Contracts.
3. WHEN the database migration runs, THE System SHALL set Checked_Bags to 0 for all existing Trip_Contracts.
4. WHILE a Trip_Contract has default luggage values and a Passenger_Count of 1, THE Flight_Options_Display SHALL render prices identically to the current behavior.
