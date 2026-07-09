# Flight Deal Tracker

A Dockerized application that monitors flight prices for user-defined travel windows, provides LLM-powered purchase timing recommendations, and delivers results through a web dashboard and email notifications. Supports a tiered airline preference system (Delta > American/United/Southwest > others), per-trip target price alerts, and targets main cabin fares while surfacing premium upgrade opportunities.

**Key features**

- Tracks prices across each trip's actual travel window (sampled departure dates, plus return legs for round trips)
- Claude-powered buy/wait/rising recommendations with per-departure-date price charts
- Target price alerts: get emailed the moment a main cabin fare drops below your number
- One combined alert email per collection cycle; separate daily digest email
- Multiple flight data sources with automatic fallback and per-source monthly quota budgets
- Booking-horizon aware: trips more than ~330 days out are "prepared" at zero API cost and start tracking automatically once airlines publish fares
- Self-maintaining: expired trips auto-archive, old snapshots are pruned, and you get a warning email if collection silently stops

## Architecture Overview

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Strawberry GraphQL |
| Frontend | React, Vite, Apollo Client, TypeScript |
| Database | PostgreSQL 16 |
| Orchestration | Docker Compose |
| Scheduler | APScheduler (in-process) |
| LLM | Anthropic Claude (Messages API) |
| Flight data | SerpAPI → SearchAPI.io → Amadeus → Travelpayouts (fallback chain) |

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

## Quick Start

You only need Docker installed. Three steps:

1. **Create your config file** — copy the template and fill in the values marked REQUIRED (email settings + Anthropic API key; a free [SerpAPI](https://serpapi.com) key is strongly recommended for real flight prices):

```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

Then open `.env` in any text editor and follow the comments.

2. **Build and start everything:**

```bash
docker compose up --build -d
```

The first build takes a few minutes. The database, backend, and web dashboard all start together.

3. **Open the dashboard:** http://localhost:3000

That's it — create a trip in the dashboard and the app checks prices every 6 hours and emails you when it's a good time to buy.

To stop: `docker compose down` (your data is kept). To update after pulling new code: `docker compose up --build -d`.

## Environment Variables

All configuration lives in `.env` (see `.env.example` for the annotated template).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMTP_HOST` | **Yes** | — | SMTP server hostname (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | No | `465` | SMTP port (465 = TLS, 587 = STARTTLS — both work) |
| `SMTP_USERNAME` | **Yes** | — | SMTP authentication username |
| `SMTP_PASSWORD` | **Yes** | — | SMTP password (for Gmail: an [app password](https://myaccount.google.com/apppasswords)) |
| `NOTIFICATION_EMAIL` | **Yes** | — | Email address to receive deal notifications |
| `LLM_API_KEY` | **Yes** | — | Anthropic API key ([console.anthropic.com](https://console.anthropic.com)) |
| `LLM_MODEL` | No | `claude-sonnet-4-6` | Claude model identifier |
| `LLM_BASE_URL` | No | `https://api.anthropic.com/v1` | Anthropic API base URL |
| `SERPAPI_KEY` | Recommended | — | [SerpAPI](https://serpapi.com) key — primary source, live Google Flights data |
| `SEARCHAPI_KEY` | No | — | [SearchAPI.io](https://www.searchapi.io) key — fallback source, live Google Flights data |
| `TRAVELPAYOUTS_TOKEN` | No | — | [Travelpayouts](https://www.travelpayouts.com) token — free cached-price fallback |
| `AMADEUS_API_KEY` / `AMADEUS_API_SECRET` | No | — | Amadeus GDS source (Self-Service API being decommissioned by Amadeus in 2026) |
| `SERPAPI_MONTHLY_BUDGET` | No | `250` | Monthly search cap for SerpAPI (0 = unlimited); at the cap the next source takes over |
| `SEARCHAPI_MONTHLY_BUDGET` | No | `100` | Monthly search cap for SearchAPI.io |
| `AMADEUS_MONTHLY_BUDGET` | No | `2000` | Monthly search cap for Amadeus |
| `SNAPSHOT_RETENTION_DAYS` | No | `180` | Delete price snapshots older than this (0 disables pruning) |
| `DIGEST_ENABLED` | No | `true` | Send a daily digest email |
| `DIGEST_HOUR_UTC` | No | `17` | UTC hour to send the digest |
| `PRIMARY_AIRLINES` | No | `DL` | Comma-separated primary airline codes |
| `SECONDARY_AIRLINES` | No | `AA,UA,WN` | Comma-separated secondary airline codes |
| `SECONDARY_THRESHOLD` | No | `0.15` | Price threshold (15%) for secondary airline inclusion |
| `TERTIARY_THRESHOLD` | No | `0.30` | Price threshold (30%) for tertiary airline inclusion |
| `PREMIUM_HIGHLIGHT_THRESHOLD` | No | `0.40` | Premium fare highlight threshold (within 40% of main cabin) |
| `COLLECTION_HOUR_UTC` | No | `13` | UTC hour of the daily economy price collection (auto catch-up at startup if >26h stale) |
| `PREMIUM_COLLECTION_WEEKDAY` | No | `tue` | Day(s) for the weekly premium-fare collection (cron syntax, e.g. `mon,thu`) |
| `PREMIUM_COLLECTION_HOUR_UTC` | No | `13` | UTC hour for the premium-fare collection (auto catch-up at startup if >8 days stale) |
| `CLOSEIN_WINDOW_DAYS` | No | `14` | Trips departing within this many days get a second daily economy collection |
| `CLOSEIN_COLLECTION_HOUR_UTC` | No | `1` | UTC hour of the close-in evening collection (free while no trip is close-in) |
| `MAX_DATES_PER_TRIP` | No | `3` | Max departure dates sampled from each trip's travel window per cycle |
| `MAX_SEARCH_DATES_PER_ROUTE` | No | `6` | Cap on searched dates per route per cycle (bounds API quota usage) |
| `BOOKING_HORIZON_DAYS` | No | `330` | Dates further out are not searched (airlines don't publish fares that far ahead); trips beyond it are "prepared" and start tracking automatically once in range |

`DATABASE_URL` is set automatically by docker-compose — leave it out of `.env` unless you run the backend outside Docker.

### Collection cadence & API quota (SerpAPI)

Fare changes flow through ATPCO continuously — there is no specific hour when prices update — so intra-day polling mostly re-reads the same prices. The tracker therefore collects **economy once daily** (default 13:00 UTC, after overnight repricing and before the morning digest) and **premium once weekly** (Tuesdays by default; premium fares move slowly and cost 3 searches per date). Trips departing within **14 days** automatically get a **second daily evening collection**, since prices move fast close to departure. The dashboard's **RUN SCAN** button always does an immediate full refresh of all cabins when you want fresh numbers right now.

Rough monthly usage (1 SerpAPI request per date per cabin class):

```
requests/month ≈ dates × 30          # daily economy
              + dates × 3 × 4.3      # weekly premium (3 classes)
              + manual scans × dates × 4
```

Example: 3 in-range search dates ≈ 90 + 39 ≈ **130/month**, which fits the free 250 tier with room for manual scans. Add fallback source keys (`SEARCHAPI_KEY`, `TRAVELPAYOUTS_TOKEN`) so collection continues if a budget runs out.

## Accessing the App

### Web Dashboard

Open http://localhost:3000 in your browser. The dashboard provides:

- A list of all active trip requests
- Price history charts showing trends over time
- LLM-powered buy/wait/rising recommendations
- Top 1–3 flight options per trip (main cabin and premium separated)
- Create, edit, and delete trip requests directly

### GraphQL Playground

Open http://localhost:8001/graphql (or http://localhost:3000/graphql via the frontend proxy) to explore the API interactively. Example query:

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
docker compose build

# Start all services (detached)
docker compose up -d

# Start with rebuild
docker compose up --build -d

# View logs
docker compose logs -f

# View logs for a specific service
docker compose logs -f app
docker compose logs -f frontend
docker compose logs -f db

# Stop all services
docker compose down

# Stop and remove volumes (deletes database data)
docker compose down -v

# Restart a single service
docker compose restart app
```

## Health & Monitoring

- `GET http://localhost:8001/health` — liveness
- `GET http://localhost:8001/health/db` — database connectivity
- `GET http://localhost:8001/health/full` — scheduler status, active trips, configured sources, **last collection time / staleness flag**, and **API quota usage this month**

If price collection silently stops (expired API key, all sources failing), the app emails `NOTIFICATION_EMAIL` a warning — at most once per 24 hours.

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/
```

CI runs the suite plus both Docker image builds on every push (`.github/workflows/docker-build.yml`).

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
│   │   └── sources/            # Data source plugins (fallback chain)
│   │       ├── serpapi_source.py       # 1. SerpAPI (live Google Flights)
│   │       ├── searchapi_source.py     # 2. SearchAPI.io (live Google Flights)
│   │       ├── amadeus_source.py       # 3. Amadeus GDS
│   │       ├── travelpayouts_source.py # 4. Travelpayouts (cached, free)
│   │       └── example_source.py       # Stub used when no keys configured
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
├── tests/                      # Pytest suite (run: pytest tests/)
├── .github/workflows/          # CI: tests + Docker builds on every push
├── docker-compose.yml          # Service orchestration
├── Dockerfile                  # Backend container image (non-root)
├── requirements.txt            # Python dependencies (pinned)
├── requirements-dev.txt        # Dev dependencies (pytest)
├── .env.example                # Configuration template (copy to .env)
└── .env                        # Your configuration (not committed)
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

2. **Register the source** in the source-chain block of `_run_collection_for_classes()` in `app/main.py`, positioned by reliability (the collector tries sources in list order and stops at the first one that returns results for a date). Optionally give it a monthly budget in the `budgets` dict passed to `CollectionService`.

The `FlightDataSource` interface requires two methods:
- `search_flights(origin, destination, departure_date, airline_filter)` — returns `list[FlightPrice]`
- `supported_airlines()` — returns `list[str]` of IATA airline codes

See `app/collector/sources/example_source.py` for a reference stub implementation.
