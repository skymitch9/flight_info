# Flight Deal Tracker

A Dockerized application that monitors flight prices for user-defined travel windows, provides LLM-powered purchase timing recommendations, and delivers results through a web dashboard and email notifications. Supports a tiered airline preference system (Delta > American/United/Southwest > others) and targets main cabin fares while surfacing premium upgrade opportunities.

## Architecture Overview

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Strawberry GraphQL |
| Frontend | React, Vite, Apollo Client, TypeScript |
| Database | PostgreSQL 16 |
| Orchestration | Docker Compose |
| Scheduler | APScheduler (in-process) |
| LLM | OpenAI-compatible API (configurable) |

```
┌─────────────────────────────────────────────────────────┐
│ Docker Compose                                          │
│                                                         │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────┐ │
│  │  Frontend    │  │  App (Backend)   │  │ Postgres │ │
│  │  React/Vite  │  │  FastAPI/GraphQL │  │   DB     │ │
│  │  port 3000   │  │  port 8000       │  │          │ │
│  └──────┬───────┘  └────────┬─────────┘  └────┬─────┘ │
│         │    GraphQL API     │    asyncpg       │       │
│         └────────────────────┼──────────────────┘       │
│                              │                          │
│                    ┌─────────┴─────────┐                │
│                    │  APScheduler      │                │
│                    │  (every 6 hours)  │                │
│                    └─────────┬─────────┘                │
│                              │                          │
└──────────────────────────────┼──────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     Flight Data Sources   LLM Provider   Email (SMTP)
```

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)

## Environment Variables

All configuration is read from environment variables. Create a `.env` file in the project root.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `postgresql+asyncpg://postgres:postgres@db:5432/flight_tracker` | PostgreSQL connection string |
| `SMTP_HOST` | **Yes** | — | SMTP server hostname |
| `SMTP_PORT` | No | `587` | SMTP server port |
| `SMTP_USERNAME` | **Yes** | — | SMTP authentication username |
| `SMTP_PASSWORD` | **Yes** | — | SMTP authentication password |
| `NOTIFICATION_EMAIL` | **Yes** | — | Email address to receive deal notifications |
| `LLM_API_KEY` | **Yes** | — | API key for the LLM provider |
| `LLM_MODEL` | No | `gpt-4o-mini` | LLM model identifier |
| `LLM_BASE_URL` | No | `https://api.openai.com/v1` | LLM API base URL (change for other providers) |
| `PRIMARY_AIRLINES` | No | `DL` | Comma-separated primary airline codes |
| `SECONDARY_AIRLINES` | No | `AA,UA,WN` | Comma-separated secondary airline codes |
| `SECONDARY_THRESHOLD` | No | `0.15` | Price threshold (15%) for secondary airline inclusion |
| `TERTIARY_THRESHOLD` | No | `0.30` | Price threshold (30%) for tertiary airline inclusion |
| `PREMIUM_HIGHLIGHT_THRESHOLD` | No | `0.40` | Premium fare highlight threshold (within 40% of main cabin) |
| `COLLECTION_INTERVAL_HOURS` | No | `6` | Hours between price collection runs |

## Quick Start

1. **Create a `.env` file** in the project root:

```env
SMTP_HOST=smtp.gmail.com
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
NOTIFICATION_EMAIL=your-email@gmail.com
LLM_API_KEY=sk-your-openai-api-key
```

2. **Build and start all services:**

```bash
docker-compose up --build
```

3. **Access the application:**
   - Dashboard: http://localhost:3000
   - GraphQL Playground: http://localhost:8000/graphql

## Accessing the App

### Web Dashboard

Open http://localhost:3000 in your browser. The dashboard provides:

- A list of all active trip requests
- Price history charts showing trends over time
- LLM-powered buy/wait/rising recommendations
- Top 1–3 flight options per trip (main cabin and premium separated)
- Create, edit, and delete trip requests directly

### GraphQL Playground

Open http://localhost:8000/graphql to explore the API interactively. Example query:

```graphql
query {
  trips {
    id
    origin
    destination
    earliestDeparture
    latestDeparture
    latestAnalysis {
      recommendation
      explanation
    }
    topFlightOptions {
      airline
      flightNumber
      priceCents
      fareClass
    }
  }
}
```

## Docker Commands

```bash
# Build all containers
docker-compose build

# Start all services (detached)
docker-compose up -d

# Start with rebuild
docker-compose up --build

# View logs
docker-compose logs -f

# View logs for a specific service
docker-compose logs -f app
docker-compose logs -f frontend
docker-compose logs -f db

# Stop all services
docker-compose down

# Stop and remove volumes (deletes database data)
docker-compose down -v

# Restart a single service
docker-compose restart app
```

## Project Structure

```
flight_info/
├── app/                        # Python backend
│   ├── main.py                 # FastAPI entrypoint, scheduler setup
│   ├── config.py               # Pydantic settings (env vars)
│   ├── database.py             # SQLAlchemy async engine & session
│   ├── models.py               # SQLAlchemy ORM models
│   ├── graphql_api/            # Strawberry GraphQL schema & resolvers
│   │   └── schema.py
│   ├── trip_manager/           # Trip CRUD business logic
│   │   └── service.py
│   ├── collector/              # Flight price data collection
│   │   ├── base.py             # FlightDataSource abstract interface
│   │   ├── service.py          # Collection orchestrator
│   │   └── sources/            # Data source plugins
│   │       └── example_source.py
│   ├── analyzer/               # LLM-powered price analysis
│   │   ├── service.py
│   │   └── prompts.py
│   ├── notifier/               # Email notification delivery
│   │   ├── service.py
│   │   └── templates/
│   ├── tiers/                  # Airline tier classification engine
│   │   └── engine.py
│   └── llm/                    # LLM client abstraction
│       └── client.py
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── App.tsx
│   │   ├── graphql/            # Apollo queries & mutations
│   │   ├── components/         # Reusable UI components
│   │   └── pages/              # Route-level page components
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── docker-compose.yml          # Service orchestration
├── Dockerfile                  # Backend container image
├── requirements.txt            # Python dependencies
└── .env                        # Environment variables (not committed)
```

## Adding New Flight Data Sources

The collector uses a plugin architecture. To add a new data source:

1. **Create a new file** in `app/collector/sources/`:

```python
# app/collector/sources/my_airline_source.py
from datetime import date
from app.collector.base import FlightDataSource, FlightPrice


class MyAirlineSource(FlightDataSource):
    """Fetches flight data from My Airline's API."""

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        airline_filter: list[str] | None = None,
    ) -> list[FlightPrice]:
        # Implement API calls or scraping logic here
        # Return a list of FlightPrice dataclass instances
        ...

    def supported_airlines(self) -> list[str]:
        return ["XX"]  # Your airline's IATA code(s)
```

2. **Register the source** in the collector service initialization (in `app/main.py` or wherever sources are configured).

The `FlightDataSource` interface requires two methods:
- `search_flights(origin, destination, departure_date, airline_filter)` — returns `list[FlightPrice]`
- `supported_airlines()` — returns `list[str]` of IATA airline codes

See `app/collector/sources/example_source.py` for a reference stub implementation.
