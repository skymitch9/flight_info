"""Flight Deal Tracker - FastAPI application entry point.

Wires all modules together: Settings, Database, TierEngine, LLMClient,
PriceAnalyzer, CollectionService, NotificationService. Configures structlog
for structured JSON logging and sets up the APScheduler for periodic
price collection.
"""

import os
import sys
from contextlib import asynccontextmanager

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from app.config import Settings
from app.graphql_api.schema import graphql_router


def _configure_structlog() -> None:
    """Configure structlog for structured JSON output in production."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


_configure_structlog()

logger = structlog.get_logger()

REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "SMTP_HOST",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "NOTIFICATION_EMAIL",
    "LLM_API_KEY",
]


def validate_config() -> None:
    """Validate that all required environment variables are present.

    Logs missing variable names and exits with non-zero code if any are absent.
    """
    missing = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
    if missing:
        logger.error(
            "Missing required configuration variables",
            missing_vars=missing,
        )
        sys.exit(1)
    logger.info("Configuration validated successfully")


# Global scheduler instance so other modules can add jobs (e.g., on trip creation)
scheduler = AsyncIOScheduler()


def _build_tier_config(settings: Settings) -> dict:
    """Build TierEngine config dict from application Settings.

    Parses comma-separated airline code strings into lists and maps
    threshold values from Settings.
    """
    return {
        "primary": [code.strip() for code in settings.primary_airlines.split(",")],
        "secondary": [code.strip() for code in settings.secondary_airlines.split(",")],
        "secondary_threshold": settings.secondary_threshold,
        "tertiary_threshold": settings.tertiary_threshold,
        "premium_highlight_threshold": settings.premium_highlight_threshold,
    }


async def _run_collection() -> None:
    """Execute a price collection cycle for main cabin (economy) fares.

    Creates fully-wired services: CollectionService with ExampleFlightSource,
    PriceAnalyzer with LLMClient, and NotificationService. After collection
    and analysis, sends notifications if appropriate.
    """
    await _run_collection_for_classes(travel_classes=[1])


async def _run_premium_collection() -> None:
    """Execute a price collection cycle for premium fares (premium economy, business, first).

    Runs once daily to conserve API quota while still tracking premium fare prices.
    """
    await _run_collection_for_classes(travel_classes=[2, 3, 4])
    logger.info("premium_fare_collection_complete")


async def _run_collection_for_classes(travel_classes: list[int]) -> None:
    """Execute a price collection cycle for specified travel classes."""
    from app.analyzer.service import PriceAnalyzer
    from app.collector.service import CollectionService
    from app.collector.sources.amadeus_source import AmadeusFlightSource
    from app.collector.sources.example_source import ExampleFlightSource
    from app.collector.sources.serpapi_source import SerpAPIFlightSource
    from app.database import async_session_factory
    from app.llm.client import LLMClient
    from app.models import TripRequest
    from app.notifier.service import NotificationService
    from app.tiers.engine import TierEngine

    settings = Settings()

    # Build tier config from settings
    tier_config = _build_tier_config(settings)
    tier_engine = TierEngine(config=tier_config)

    # Initialize LLM client
    llm_client = LLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )

    # Initialize PriceAnalyzer
    price_analyzer = PriceAnalyzer(
        llm_client=llm_client,
        session_factory=async_session_factory,
    )

    # Initialize NotificationService
    notification_service = NotificationService(
        settings=settings,
        session_factory=async_session_factory,
        tier_engine=tier_engine,
    )

    # Initialize CollectionService — prefer SerpAPI, fallback to Amadeus, then stub
    sources = []
    if settings.serpapi_key:
        sources.append(SerpAPIFlightSource(api_key=settings.serpapi_key, travel_classes=travel_classes))
        logger.info("serpapi_source_configured", travel_classes=travel_classes)
    elif settings.amadeus_api_key and settings.amadeus_api_secret:
        sources.append(
            AmadeusFlightSource(
                api_key=settings.amadeus_api_key,
                api_secret=settings.amadeus_api_secret,
                use_production=settings.amadeus_production,
            )
        )
        logger.info("amadeus_source_configured")
    else:
        sources.append(ExampleFlightSource())
        logger.warning("no_flight_api_credentials_using_stub_source")

    collection_service = CollectionService(
        sources=sources,
        session_factory=async_session_factory,
        analyzer=price_analyzer,
    )

    try:
        # Run collection (collects prices, stores snapshots, runs analysis)
        await collection_service.collect_all()
        logger.info("scheduled_collection_complete")

        # After analysis, check if notifications should be sent
        # Fetch active trips and their latest analysis to notify
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        async with async_session_factory() as session:
            # Get the latest analysis for each active trip
            stmt = (
                select(TripRequest)
                .where(TripRequest.is_active == True)  # noqa: E712
                .options(selectinload(TripRequest.analysis_results))
            )
            result = await session.execute(stmt)
            trips = result.scalars().all()

            for trip in trips:
                if not trip.analysis_results:
                    continue
                latest_analysis = max(
                    trip.analysis_results, key=lambda a: a.analyzed_at
                )

                # Get the latest price snapshots for this trip
                from app.models import PriceSnapshot

                snap_stmt = (
                    select(PriceSnapshot)
                    .where(PriceSnapshot.trip_request_id == trip.id)
                    .order_by(PriceSnapshot.collected_at.desc())
                )
                snap_result = await session.execute(snap_stmt)
                snapshots = snap_result.scalars().all()

                # Convert snapshots to FlightPrice objects for the notifier
                from app.collector.base import FlightPrice

                prices = [
                    FlightPrice(
                        airline=s.airline_code,
                        flight_number=s.flight_number,
                        departure_time=s.departure_time,
                        arrival_time=s.arrival_time,
                        fare_class=s.fare_class,
                        price_cents=s.price_cents,
                        origin=trip.origin,
                        destination=trip.destination,
                        departure_date=s.flight_date,
                    )
                    for s in snapshots
                ]

                await notification_service.notify_if_appropriate(
                    trip=trip,
                    analysis=latest_analysis,
                    prices=prices,
                )

    except Exception as exc:
        logger.error("scheduled_collection_failed", error=str(exc))


def trigger_early_collection() -> None:
    """Schedule an immediate one-off collection run.

    Call this when a new trip is created to ensure price data is collected
    within 15 minutes rather than waiting for the next scheduled interval.
    The job is added with `replace_existing=True` so multiple rapid trip
    creations don't queue redundant runs.
    """
    scheduler.add_job(
        _run_collection,
        trigger=IntervalTrigger(minutes=1),
        id="early_collection",
        name="Early collection after trip creation",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("early_collection_scheduled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing startup and shutdown events."""
    validate_config()
    logger.info("Flight Deal Tracker starting up")

    # Initialize database tables
    from app.database import create_tables

    await create_tables()
    logger.info("Database tables initialized")

    # Configure and start the scheduler
    settings = Settings()
    scheduler.add_job(
        _run_collection,
        trigger=IntervalTrigger(hours=settings.collection_interval_hours),
        id="price_collection",
        name="Periodic price collection (main cabin)",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _run_premium_collection,
        trigger=IntervalTrigger(hours=24),
        id="premium_price_collection",
        name="Daily premium fare collection (business, first, premium economy)",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Scheduler started",
        collection_interval_hours=settings.collection_interval_hours,
    )

    yield

    # Graceful shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shut down")
    logger.info("Flight Deal Tracker shutting down")


app = FastAPI(title="Flight Deal Tracker", lifespan=lifespan)

# Mount GraphQL endpoint at /graphql
app.include_router(graphql_router, prefix="/graphql")


# --- Health Check Endpoints ---


@app.get("/health")
async def health_check():
    """Basic health check — confirms the app is running."""
    return {"status": "ok", "service": "flight-deal-tracker"}


@app.get("/health/db")
async def health_check_db():
    """Database health check — confirms DB connectivity."""
    from app.database import async_session_factory
    from sqlalchemy import text

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "error", "database": str(exc)}


@app.get("/health/full")
async def health_check_full():
    """Full system health check — DB, scheduler, and config."""
    from app.database import async_session_factory
    from sqlalchemy import text, select
    from app.models import TripRequest

    checks = {}

    # DB connectivity
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    # Scheduler running
    checks["scheduler"] = "running" if scheduler.running else "stopped"

    # Active trips count
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(TripRequest).where(TripRequest.is_active == True)  # noqa: E712
            )
            trips = result.scalars().all()
            checks["active_trips"] = len(trips)
    except Exception:
        checks["active_trips"] = "error"

    # Config loaded
    try:
        settings = Settings()
        checks["serpapi"] = "configured" if settings.serpapi_key else "not configured"
        checks["llm"] = "configured" if settings.llm_api_key else "not configured"
    except Exception:
        checks["config"] = "error"

    overall = "ok" if checks.get("database") == "ok" and checks.get("scheduler") == "running" else "degraded"
    return {"status": overall, "checks": checks}
