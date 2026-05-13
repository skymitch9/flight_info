# Implementation Plan: Flight Deal Tracker

## Overview

Build a full-stack Dockerized flight deal tracker with a Python/FastAPI/Strawberry GraphQL backend, React/Vite/Apollo Client frontend, and PostgreSQL database. The backend handles trip management, scheduled price collection, LLM-powered analysis, and email notifications. The frontend provides a dashboard for viewing trips, price history, and recommendations. Docker Compose orchestrates three services: app, frontend, and db.

## Tasks

- [x] 1. Set up backend project structure and configuration
  - [x] 1.1 Create backend directory structure and dependency files
    - Create `app/` directory with `__init__.py` files for all subpackages: `graphql_api/`, `trip_manager/`, `collector/`, `collector/sources/`, `analyzer/`, `notifier/`, `notifier/templates/`, `tiers/`, `llm/`
    - Create `requirements.txt` with: fastapi, uvicorn, strawberry-graphql[fastapi], sqlalchemy[asyncio], asyncpg, pydantic-settings, httpx, apscheduler, structlog, aiosmtplib, jinja2
    - _Requirements: 6.1, 7.1_

  - [x] 1.2 Implement application configuration module
    - Create `app/config.py` with Pydantic `BaseSettings` class
    - Include all settings: DATABASE_URL, SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, NOTIFICATION_EMAIL, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL, PRIMARY_AIRLINES, SECONDARY_AIRLINES, SECONDARY_THRESHOLD, TERTIARY_THRESHOLD, PREMIUM_HIGHLIGHT_THRESHOLD, COLLECTION_INTERVAL_HOURS
    - Support `.env` file loading
    - _Requirements: 6.3_

  - [x] 1.3 Implement startup validation and FastAPI app entry point
    - Create `app/main.py` with FastAPI app initialization
    - Implement `validate_config()` that checks all required environment variables on startup and logs missing variable names before exiting with non-zero code
    - Wire up lifespan event for startup validation
    - _Requirements: 6.4_

- [x] 2. Implement database layer
  - [x] 2.1 Create SQLAlchemy async engine and session setup
    - Create `app/database.py` with async engine creation using `DATABASE_URL`
    - Implement async session factory and dependency injection helper
    - Implement `create_tables()` utility for initial schema creation
    - _Requirements: 6.5_

  - [x] 2.2 Create SQLAlchemy ORM models
    - Create `app/models.py` with models: `TripRequest`, `PriceSnapshot`, `AnalysisResult`, `Notification`
    - Define relationships between models (TripRequest has many PriceSnapshots, AnalysisResults, Notifications)
    - Include all columns per the design schema (origin, destination, dates, is_active, timestamps, etc.)
    - _Requirements: 1.1, 1.2, 4.2, 6.5_

- [x] 3. Implement trip management and GraphQL API
  - [x] 3.1 Implement Trip Manager service
    - Create `app/trip_manager/service.py` with `TripService` class
    - Implement `create_trip`, `list_active_trips`, `get_trip`, `update_trip`, `delete_trip` methods
    - Implement `_validate` method enforcing: valid 3-letter IATA codes, future dates, date ordering, required fields present
    - Raise descriptive errors for invalid input
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 3.2 Implement Strawberry GraphQL schema and resolvers
    - Create `app/graphql_api/schema.py` with Strawberry types: `TripRequestType`, `PriceSnapshotType`, `AnalysisResultType`, `FlightOptionType`
    - Create `TripRequestInput` input type
    - Implement `Query` type with `trips` and `trip(trip_id)` resolvers that fetch nested price history, latest analysis, and top flight options
    - Implement `Mutation` type with `create_trip`, `update_trip`, `delete_trip` resolvers
    - Create the Strawberry schema and mount on FastAPI at `/graphql` via `GraphQLRouter`
    - _Requirements: 1.3, 7.2, 8.5, 8.6_

- [x] 4. Implement airline tier engine
  - [x] 4.1 Create airline tier classification and filtering logic
    - Create `app/tiers/engine.py` with `AirlineTier` enum and `TierEngine` class
    - Implement `classify_airline` method (Primary=DL, Secondary=AA/UA/WN, Tertiary=all others)
    - Implement `filter_options` method applying tier thresholds (15% for secondary, 30% for tertiary) and returning up to 3 options prioritizing Primary
    - Implement `identify_premium_highlights` method finding premium fares within 40% of main cabin price
    - Load thresholds from configuration
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.3_

- [x] 5. Implement data collection module
  - [x] 5.1 Create flight data source plugin interface
    - Create `app/collector/base.py` with `FlightPrice` dataclass and `FlightDataSource` abstract base class
    - Define `search_flights` and `supported_airlines` abstract methods
    - Create `app/collector/sources/example_source.py` as a reference implementation stub
    - _Requirements: 7.3_

  - [x] 5.2 Implement collection service
    - Create `app/collector/service.py` with `CollectionService` class
    - Implement `collect_all` method that iterates active trip requests, collects prices from all sources, stores snapshots, and triggers analysis
    - Handle source failures gracefully (log warning, continue with other sources)
    - _Requirements: 4.1, 4.2, 7.3_

- [x] 6. Implement LLM client and price analysis module
  - [x] 6.1 Create LLM client
    - Create `app/llm/client.py` with `LLMClient` class using httpx
    - Implement `complete` method that sends prompts to OpenAI-compatible API
    - Configure with api_key, model, and base_url from settings
    - Handle timeouts and HTTP errors
    - _Requirements: 4.4_

  - [x] 6.2 Implement price analysis service
    - Create `app/analyzer/service.py` with `Recommendation` enum and `PriceAnalyzer` class
    - Create `app/analyzer/prompts.py` with prompt template that includes price history, current prices, days until departure, and route context
    - Implement `analyze` method: fetch history, build prompt, call LLM, parse response, store result
    - Implement `_parse_response` that extracts recommendation (buy_now/wait/prices_rising) and explanation, defaulting to "wait" if unparseable
    - _Requirements: 4.3, 4.4, 4.5_

- [x] 7. Implement notification module
  - [x] 7.1 Create email notification service
    - Create `app/notifier/service.py` with `NotificationService` class
    - Implement `notify_if_appropriate` method: check recommendation (skip if "wait"), check 24-hour throttle, filter options via TierEngine, format email, send with retry
    - Implement `_send_with_retry` with 3 attempts and exponential backoff (1s, 2s, 4s)
    - Log failures after exhausting retries
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6_

  - [x] 7.2 Create email template
    - Create `app/notifier/templates/deal_notification.html` Jinja2 template
    - Include sections: recommendation explanation, Target_Fare flight options (1-3), Premium_Fare flight options (separated), airline name, flight number, departure/arrival times, price
    - _Requirements: 5.2, 5.3, 5.4_

- [x] 8. Implement APScheduler integration
  - [x] 8.1 Wire scheduler into FastAPI app
    - Add APScheduler setup in `app/main.py` lifespan
    - Schedule `CollectionService.collect_all` to run at the configured interval (default every 6 hours)
    - Ensure scheduler starts after startup validation and DB initialization
    - Ensure first collection runs within 15 minutes of a new trip being created (or at next scheduled interval)
    - _Requirements: 1.4, 4.1_

- [x] 9. Checkpoint
  - Ensure the backend runs with `uvicorn app.main:app`, the GraphQL playground is accessible at `/graphql`, and trip CRUD mutations work. Ask the user if questions arise.

- [x] 10. Set up frontend project
  - [x] 10.1 Initialize React + Vite + TypeScript project
    - Create `frontend/` directory with Vite React-TS template
    - Install dependencies: react, react-dom, react-router-dom, @apollo/client, graphql, recharts
    - Create `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`
    - _Requirements: 8.6_

  - [x] 10.2 Configure Apollo Client and routing
    - Create `frontend/src/graphql/client.ts` with Apollo Client pointing to `/graphql` (relative, proxied by nginx)
    - Create `frontend/src/App.tsx` with ApolloProvider and BrowserRouter
    - Set up routes: `/` → TripList, `/trips/:id` → TripDetail
    - Create `frontend/src/main.tsx` entry point
    - _Requirements: 8.6, 8.7_

  - [x] 10.3 Define GraphQL query and mutation documents
    - Create `frontend/src/graphql/queries.ts` with: GET_TRIPS, GET_TRIP_DETAIL, CREATE_TRIP, UPDATE_TRIP, DELETE_TRIP
    - Include all fields needed by the dashboard views (nested price history, analysis, flight options)
    - _Requirements: 8.6_

- [x] 11. Implement frontend pages and components
  - [x] 11.1 Build Trip List page
    - Create `frontend/src/pages/TripList.tsx`
    - Fetch and display all active trips with origin, destination, date ranges
    - Show latest recommendation badge (buy now / wait / prices rising) per trip
    - Include button/link to create new trip and navigate to trip detail
    - _Requirements: 8.1, 8.3_

  - [x] 11.2 Build Trip Detail page
    - Create `frontend/src/pages/TripDetail.tsx`
    - Fetch single trip with full price history, latest analysis, and top flight options
    - Display recommendation with explanation
    - Display flight options separated into Target_Fare and Premium_Fare sections
    - Include edit and delete actions
    - _Requirements: 8.2, 8.3, 8.4, 8.5_

  - [x] 11.3 Build Price Chart component
    - Create `frontend/src/components/PriceChart.tsx` using Recharts
    - Render line chart showing price over time with separate lines for main cabin and premium fares
    - _Requirements: 8.2_

  - [x] 11.4 Build Trip Form component
    - Create `frontend/src/components/TripForm.tsx` as a modal form
    - Include fields: origin, destination, earliest/latest departure, earliest/latest return (optional)
    - Validate inputs client-side (3-letter codes, date ordering)
    - Use CREATE_TRIP and UPDATE_TRIP mutations
    - _Requirements: 8.5_

  - [x] 11.5 Build supporting components
    - Create `frontend/src/components/TripCard.tsx` for trip summary display
    - Create `frontend/src/components/FlightOptions.tsx` for flight options table with fare class separation
    - _Requirements: 8.1, 8.4_

- [x] 12. Checkpoint
  - Ensure the frontend builds with `npm run build` and all pages render correctly when served. Ask the user if questions arise.

- [x] 13. Docker and deployment configuration
  - [x] 13.1 Create backend Dockerfile
    - Create `Dockerfile` in project root for the Python backend
    - Use `python:3.12-slim` base, install requirements, copy app, expose port 8000, run with uvicorn
    - _Requirements: 6.1_

  - [x] 13.2 Create frontend Dockerfile and nginx config
    - Create `frontend/Dockerfile` with multi-stage build: node:20-alpine for build, nginx:alpine for production
    - Create `frontend/nginx.conf` with SPA fallback (`try_files`) and `/graphql` proxy to `http://app:8000/graphql`
    - _Requirements: 6.1, 8.6_

  - [x] 13.3 Create docker-compose.yml
    - Define three services: `app` (backend), `frontend`, `db` (postgres:16-alpine)
    - Configure environment variables pass-through for app service
    - Set up `depends_on` with health check for db
    - Mount `pgdata` volume for database persistence
    - Expose app on port 8000, frontend on port 3000
    - _Requirements: 6.2, 6.3, 6.5_

  - [x] 13.4 Create GitHub Actions workflow for Docker build verification
    - Create `.github/workflows/docker-build.yml`
    - Trigger on push to all branches
    - Run `docker build -t flight-deal-tracker-backend .` for backend image
    - Run `docker build -t flight-deal-tracker-frontend ./frontend` for frontend image
    - _Requirements: CI Docker build check constraint_

- [x] 14. Final wiring and integration
  - [x] 14.1 Wire all modules together in app/main.py
    - Initialize Settings, Database, TripService, TierEngine, LLMClient, PriceAnalyzer, CollectionService, NotificationService
    - Connect CollectionService → PriceAnalyzer → NotificationService pipeline
    - Mount GraphQL router with access to services
    - Ensure database tables are created on startup
    - Add structured JSON logging via structlog
    - _Requirements: 7.1, 7.2_

  - [x] 14.2 Create README with setup and usage instructions
    - Document environment variables required
    - Document docker-compose usage (build, up, down)
    - Document how to access the dashboard and GraphQL playground
    - _Requirements: 6.3_

- [x] 15. Final checkpoint
  - Ensure `docker-compose up --build` starts all three services successfully, the frontend is accessible on port 3000, GraphQL playground works on port 8000, and `/graphql` proxy from frontend works. Ask the user if questions arise.

## Notes

- No automated tests are included — this is a personal project validated manually
- The GitHub Actions workflow (task 13.4) is the only CI check, verifying Docker images build on push
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The frontend communicates with the backend exclusively via the GraphQL API proxied through nginx

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "10.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "10.2", "10.3"] },
    { "id": 2, "tasks": ["2.1"] },
    { "id": 3, "tasks": ["2.2", "4.1", "5.1", "6.1"] },
    { "id": 4, "tasks": ["3.1", "5.2", "6.2"] },
    { "id": 5, "tasks": ["3.2", "7.1"] },
    { "id": 6, "tasks": ["7.2", "8.1"] },
    { "id": 7, "tasks": ["11.1", "11.3", "11.4", "11.5"] },
    { "id": 8, "tasks": ["11.2"] },
    { "id": 9, "tasks": ["13.1", "13.2", "13.3", "13.4"] },
    { "id": 10, "tasks": ["14.1", "14.2"] }
  ]
}
```
