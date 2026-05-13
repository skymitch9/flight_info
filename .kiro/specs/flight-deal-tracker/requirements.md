# Requirements Document

## Introduction

The Flight Deal Tracker is a Dockerized application that monitors flight prices for user-defined travel date ranges and notifies the user via email when prices are favorable. The application uses an LLM for price trend analysis and purchase timing recommendations. It supports a tiered airline preference system and targets main cabin fares while providing visibility into premium fare classes. A web dashboard provides real-time visibility into trips, price history, and deal recommendations without relying solely on email notifications.

## Constraints

- **No automated testing**: This is a personal project. No unit tests, integration tests, or test suites are required. Validation is done manually by the user.
- **CI Docker build check**: A GitHub Actions workflow SHALL run `docker build` on every push to verify the container image builds successfully. This is the only automated validation required.

## Glossary

- **Tracker**: The Flight Deal Tracker application responsible for monitoring prices, analyzing trends, and sending notifications
- **User**: The person configuring travel date ranges and receiving deal notifications
- **Trip_Request**: A user-defined travel date range specifying origin, destination, and acceptable travel dates
- **Airline_Tier**: A priority classification for airlines (Primary, Secondary, or Tertiary) that determines search priority and recommendation weighting
- **Primary_Airline**: Delta — the preferred airline given equal or near-equal pricing
- **Secondary_Airline**: American, United, or Southwest — used when they offer meaningfully better deals than the Primary Airline
- **Tertiary_Airline**: Any other airline (e.g., British Airways, JetBlue, Frontier) — used only when they offer significantly better deals
- **Fare_Class**: The cabin or ticket tier for a flight (Main Cabin, Business, First Class, Comfort Plus, or equivalent)
- **Target_Fare**: Main Cabin or the lowest fare class that allows seat selection
- **Premium_Fare**: Business, First Class, Comfort Plus, or equivalent upgraded fare classes
- **Price_Analysis**: The LLM-driven evaluation of current prices against historical trends to determine purchase timing
- **Deal_Notification**: An email sent to the User containing recommended flights and purchase timing guidance
- **Flight_Option**: A specific flight identified by flight number, departure time, arrival time, airline, and price
- **Dashboard**: A web-based user interface for viewing trips, price history, analysis results, and deal recommendations
- **GraphQL_API**: The application's query interface allowing the Dashboard to fetch trips with related price history, analysis, and notifications in flexible queries

## Requirements

### Requirement 1: Trip Request Management

**User Story:** As a user, I want to enter date ranges for trips I plan to take, so that the Tracker monitors prices for those specific travel windows.

#### Acceptance Criteria

1. THE Tracker SHALL allow the User to create a Trip_Request with an origin airport, destination airport, earliest departure date, and latest departure date
2. THE Tracker SHALL allow the User to create a Trip_Request with an earliest return date and latest return date for round-trip travel
3. THE Tracker SHALL allow the User to create, view, update, and delete Trip_Requests
4. WHEN a Trip_Request is created, THE Tracker SHALL begin monitoring flight prices for the specified route and date range within 15 minutes
5. IF a Trip_Request contains invalid data (past dates, invalid airport codes, or missing required fields), THEN THE Tracker SHALL reject the request and return a descriptive error message

### Requirement 2: Airline Tier Configuration

**User Story:** As a user, I want my airline preferences organized into tiers, so that the Tracker prioritizes deals from my preferred airlines.

#### Acceptance Criteria

1. THE Tracker SHALL classify airlines into three Airline_Tiers: Primary (Delta), Secondary (American, United, Southwest), and Tertiary (all other airlines)
2. WHEN presenting Flight_Options, THE Tracker SHALL weight recommendations toward Primary_Airline options unless a Secondary_Airline or Tertiary_Airline offers a meaningfully lower price
3. WHEN a Secondary_Airline offers a price at least 15% lower than the best Primary_Airline price for the same route, THE Tracker SHALL include the Secondary_Airline option in the Deal_Notification
4. WHEN a Tertiary_Airline offers a price at least 30% lower than the best Primary_Airline price for the same route, THE Tracker SHALL include the Tertiary_Airline option in the Deal_Notification

### Requirement 3: Fare Class Targeting

**User Story:** As a user, I want to primarily see main cabin prices with seat selection, while also viewing premium fare options, so that I can make informed purchasing decisions.

#### Acceptance Criteria

1. THE Tracker SHALL target the Target_Fare (Main Cabin or lowest fare class allowing seat selection) as the primary fare class for price monitoring and recommendations
2. THE Tracker SHALL retrieve and display Premium_Fare prices (Business, First Class, Comfort Plus, or equivalent) alongside Target_Fare results in each Deal_Notification
3. WHEN a Premium_Fare is within 40% of the Target_Fare price for the same flight, THE Tracker SHALL highlight the Premium_Fare as a potential upgrade opportunity in the Deal_Notification

### Requirement 4: Price Monitoring and LLM Analysis

**User Story:** As a user, I want the application to analyze flight price trends and predict good purchase timing, so that I buy tickets at favorable prices.

#### Acceptance Criteria

1. THE Tracker SHALL collect flight prices for each active Trip_Request at least every 6 hours
2. THE Tracker SHALL store historical price data for each monitored route and date combination
3. WHEN new price data is collected, THE Tracker SHALL submit the price history to the Price_Analysis module for trend evaluation
4. THE Price_Analysis module SHALL use an LLM to evaluate whether current prices represent a good buying opportunity based on historical trends, days until departure, and typical price patterns for the route
5. THE Price_Analysis module SHALL produce a recommendation of "buy now," "wait," or "prices rising — consider buying soon" for each monitored Trip_Request

### Requirement 5: Email Deal Notifications

**User Story:** As a user, I want to receive email notifications when it's a good time to buy, including specific flight options, so that I can act on deals quickly.

#### Acceptance Criteria

1. WHEN the Price_Analysis module recommends "buy now" or "prices rising — consider buying soon," THE Tracker SHALL send a Deal_Notification to the User's configured email address
2. THE Deal_Notification SHALL include between 1 and 3 Flight_Options per route, each containing the airline name, flight number, departure time, arrival time, and price
3. THE Deal_Notification SHALL include the Price_Analysis recommendation and a brief explanation of why the current price is favorable
4. THE Deal_Notification SHALL separate Target_Fare options from Premium_Fare options in the email body
5. THE Tracker SHALL send no more than one Deal_Notification per Trip_Request within a 24-hour period to avoid notification fatigue
6. IF the Tracker cannot reach the email service, THEN THE Tracker SHALL retry delivery up to 3 times with exponential backoff and log the failure

### Requirement 6: Docker Deployment

**User Story:** As a user, I want the application to run in Docker, so that I can deploy and manage it easily on any host.

#### Acceptance Criteria

1. THE Tracker SHALL provide a Dockerfile that builds the application into a self-contained container image
2. THE Tracker SHALL provide a docker-compose configuration that starts all required services (application, database, scheduler)
3. THE Tracker SHALL read all configuration (email credentials, LLM API keys, airline tier thresholds) from environment variables or a mounted configuration file
4. WHEN the container starts, THE Tracker SHALL validate that all required configuration values are present and log an error with the missing variable names if any are absent
5. THE Tracker SHALL persist price history and Trip_Request data in a volume-mounted database so that data survives container restarts

### Requirement 7: Extensibility

**User Story:** As a user, I want the application designed for future feature additions, so that new capabilities can be added without major rework.

#### Acceptance Criteria

1. THE Tracker SHALL separate concerns into distinct modules: data collection, price analysis, notification delivery, and trip management
2. THE Tracker SHALL expose trip management and price data through a GraphQL_API so that the Dashboard and future clients can query data flexibly
3. THE Tracker SHALL use a plugin-compatible architecture for airline data sources so that new airlines or data providers can be added without modifying core logic

### Requirement 8: Web Dashboard

**User Story:** As a user, I want a web dashboard to view my trips, price history, and deal recommendations, so that I can monitor flight prices without relying solely on email notifications.

#### Acceptance Criteria

1. THE Dashboard SHALL display a list of all active Trip_Requests with their origin, destination, and travel date ranges
2. THE Dashboard SHALL display price history charts for each Trip_Request showing how prices have changed over time
3. THE Dashboard SHALL display the latest Price_Analysis recommendation (buy now, wait, or prices rising) for each active Trip_Request
4. THE Dashboard SHALL display the top 1-3 Flight_Options for each Trip_Request, separated into Target_Fare and Premium_Fare sections
5. THE Dashboard SHALL allow the User to create, edit, and delete Trip_Requests directly from the interface
6. THE Dashboard SHALL query data from the GraphQL_API to support flexible data fetching and reduce round-trips
7. THE Dashboard SHALL update displayed data when the User navigates to a trip or refreshes the page
