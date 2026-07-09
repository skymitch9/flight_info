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

    Runs weekly to conserve API quota — premium fares move slowly and cost
    3 searches per date.
    """
    await _run_collection_for_classes(travel_classes=[2, 3, 4])
    logger.info("premium_fare_collection_complete")


async def _run_full_collection() -> None:
    """Collect all fare classes in one pass (manual refresh).

    Used by the dashboard's refresh button — a deliberate action, so it
    grabs everything at once (4 searches per date instead of 1).
    """
    await _run_collection_for_classes(travel_classes=[1, 2, 3, 4])
    logger.info("manual_full_collection_complete")


async def _run_daily_digest() -> None:
    """Send the daily flight digest email."""
    from app.database import async_session_factory
    from app.notifier.digest import DailyDigestService

    settings = Settings()
    digest_service = DailyDigestService(
        settings=settings,
        session_factory=async_session_factory,
    )
    await digest_service.send_daily_digest()


async def _run_maintenance() -> None:
    """Daily maintenance: archive expired trips and prune old snapshots."""
    from datetime import date, datetime, timedelta

    from sqlalchemy import delete, select, update

    from app.database import async_session_factory
    from app.models import PriceSnapshot, TripRequest

    settings = Settings()

    async with async_session_factory() as session:
        # Archive trips whose entire departure window has passed — they move
        # to the history view and stop consuming collection quota.
        result = await session.execute(
            update(TripRequest)
            .where(
                TripRequest.status == "active",
                TripRequest.is_active == True,  # noqa: E712
                TripRequest.latest_departure < date.today(),
            )
            .values(is_active=False, status="expired")
        )
        if result.rowcount:
            logger.info("trips_auto_expired", count=result.rowcount)

        # Prune snapshots past the retention window to keep queries fast
        if settings.snapshot_retention_days > 0:
            cutoff = datetime.utcnow() - timedelta(days=settings.snapshot_retention_days)
            result = await session.execute(
                delete(PriceSnapshot).where(PriceSnapshot.collected_at < cutoff)
            )
            if result.rowcount:
                logger.info(
                    "snapshots_pruned",
                    count=result.rowcount,
                    retention_days=settings.snapshot_retention_days,
                )

        await session.commit()


# In-memory throttle for staleness alerts (at most one per 24h per process)
_last_staleness_alert = None


async def _check_collection_staleness() -> None:
    """Alert by email when collection has silently stopped producing data.

    Considered stale when the newest route collection is older than twice the
    collection interval while at least one active trip is within the booking
    horizon (i.e. collection *should* be happening).
    """
    global _last_staleness_alert
    from datetime import date, datetime, timedelta

    from sqlalchemy import func, select

    from app.database import async_session_factory
    from app.models import Route, TripRequest

    settings = Settings()

    async with async_session_factory() as session:
        last_collected = (
            await session.execute(select(func.max(Route.last_collected_at)))
        ).scalar()

        horizon_end = date.today() + timedelta(days=settings.booking_horizon_days)
        collectable_trips = (
            await session.execute(
                select(func.count(TripRequest.id)).where(
                    TripRequest.status == "active",
                    TripRequest.is_active == True,  # noqa: E712
                    TripRequest.earliest_departure <= horizon_end,
                    TripRequest.latest_departure >= date.today(),
                )
            )
        ).scalar()

    if not collectable_trips or last_collected is None:
        return  # nothing should be collecting — silence is expected

    staleness = datetime.utcnow() - last_collected
    # Daily cadence + generous slack for downtime around the cron hour
    threshold = timedelta(hours=30)
    if staleness <= threshold:
        return

    if _last_staleness_alert and datetime.utcnow() - _last_staleness_alert < timedelta(hours=24):
        return  # already alerted recently

    logger.error(
        "collection_stale",
        last_collected=str(last_collected),
        staleness_hours=round(staleness.total_seconds() / 3600, 1),
    )

    from email.mime.text import MIMEText

    import aiosmtplib

    hours = round(staleness.total_seconds() / 3600)
    message = MIMEText(
        f"Flight Deal Tracker has not collected any prices in {hours} hours "
        f"(expected daily at {settings.collection_hour_utc}:00 UTC).\n\n"
        "Likely causes: expired/exhausted API keys, all data sources failing, "
        "or a scheduler problem. Check the app logs:\n"
        "  docker compose logs app | grep -E 'source_failed|source_budget_exhausted|collection'\n"
    )
    message["From"] = settings.smtp_username
    message["To"] = settings.notification_email
    message["Subject"] = f"⚠ Flight Tracker: price collection stale ({hours}h)"

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_port == 465,
            start_tls=settings.smtp_port != 465,
        )
        _last_staleness_alert = datetime.utcnow()
        logger.info("staleness_alert_sent")
    except Exception as exc:
        logger.error("staleness_alert_failed", error=str(exc))


async def _run_collection_for_classes(travel_classes: list[int]) -> None:
    """Execute a price collection cycle for specified travel classes."""
    from app.analyzer.service import PriceAnalyzer
    from app.collector.service import CollectionService
    from app.collector.sources.amadeus_source import AmadeusFlightSource
    from app.collector.sources.example_source import ExampleFlightSource
    from app.collector.sources.searchapi_source import SearchAPIFlightSource
    from app.collector.sources.serpapi_source import SerpAPIFlightSource
    from app.collector.sources.travelpayouts_source import TravelpayoutsFlightSource
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

    # Build the source chain in reliability order — the first source that
    # returns results for a date wins; the rest are fallbacks used on error,
    # empty results, or an exhausted monthly budget.
    #   1. SerpAPI      — live Google Flights scrape (best data)
    #   2. SearchAPI.io — live Google Flights scrape (equivalent data)
    #   3. Amadeus      — real GDS, but limited test data (Self-Service API
    #                     is being decommissioned by Amadeus in 2026)
    #   4. Travelpayouts — free cached prices (hours-to-days old, economy only)
    sources = []
    if settings.serpapi_key:
        sources.append(SerpAPIFlightSource(api_key=settings.serpapi_key, travel_classes=travel_classes))
    if settings.searchapi_key:
        sources.append(SearchAPIFlightSource(api_key=settings.searchapi_key, travel_classes=travel_classes))
    if settings.amadeus_api_key and settings.amadeus_api_secret:
        sources.append(
            AmadeusFlightSource(
                api_key=settings.amadeus_api_key,
                api_secret=settings.amadeus_api_secret,
                use_production=settings.amadeus_production,
            )
        )
    if settings.travelpayouts_token:
        sources.append(TravelpayoutsFlightSource(token=settings.travelpayouts_token))
    if sources:
        logger.info(
            "flight_sources_configured",
            chain=[s.__class__.__name__ for s in sources],
            travel_classes=travel_classes,
        )
    else:
        sources.append(ExampleFlightSource())
        logger.warning("no_flight_api_credentials_using_stub_source")

    collection_service = CollectionService(
        sources=sources,
        session_factory=async_session_factory,
        analyzer=price_analyzer,
        max_dates_per_trip=settings.max_dates_per_trip,
        max_search_dates_per_route=settings.max_search_dates_per_route,
        booking_horizon_days=settings.booking_horizon_days,
        budgets={
            "SerpAPIFlightSource": settings.serpapi_monthly_budget,
            "SearchAPIFlightSource": settings.searchapi_monthly_budget,
            "AmadeusFlightSource": settings.amadeus_monthly_budget,
        },
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

            # Alerts across all trips are combined into a single email
            pending_alerts = []

            for trip in trips:
                if not trip.analysis_results:
                    continue
                latest_analysis = max(
                    trip.analysis_results, key=lambda a: a.analyzed_at
                )

                # Get the latest batch of price snapshots for this trip's route,
                # restricted to flights inside the trip's departure window.
                # Snapshots are stored at the route level (trip_request_id is NULL).
                from datetime import timedelta

                from app.models import PriceSnapshot

                snap_stmt = (
                    select(PriceSnapshot)
                    .where(
                        PriceSnapshot.route_id == trip.route_id
                        if trip.route_id is not None
                        else PriceSnapshot.trip_request_id == trip.id
                    )
                    .where(PriceSnapshot.flight_date >= trip.earliest_departure)
                    .where(PriceSnapshot.flight_date <= trip.latest_departure)
                    .order_by(PriceSnapshot.collected_at.desc())
                )
                snap_result = await session.execute(snap_stmt)
                all_snapshots = snap_result.scalars().all()

                # Keep only the most recent collection batch (5-minute window)
                snapshots = []
                if all_snapshots:
                    latest = all_snapshots[0].collected_at
                    cutoff = latest - timedelta(minutes=5)
                    snapshots = [s for s in all_snapshots if s.collected_at >= cutoff]

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

                # Target price check: alert when the cheapest main-cabin fare
                # (per ticket) is at or below the trip's target, regardless of
                # the LLM recommendation.
                force_reason = None
                if trip.target_price_cents:
                    main_fares = [
                        p.price_cents for p in prices if p.fare_class == "main_cabin"
                    ]
                    if main_fares and min(main_fares) <= trip.target_price_cents:
                        force_reason = (
                            f"A main cabin fare at ${min(main_fares) / 100:.0f} is at or "
                            f"below your ${trip.target_price_cents / 100:.0f} target price."
                        )

                alert = await notification_service.build_alert(
                    trip=trip,
                    analysis=latest_analysis,
                    prices=prices,
                    force_reason=force_reason,
                )
                if alert is not None:
                    pending_alerts.append(alert)

            # One email covering every trip that alerted this cycle
            await notification_service.send_alerts(pending_alerts)

    except Exception as exc:
        logger.error("scheduled_collection_failed", error=str(exc))


def trigger_early_collection() -> None:
    """Schedule an immediate one-off economy collection run.

    Call this when a trip is created/updated so baseline price data arrives
    within seconds rather than waiting for tomorrow's scheduled run. Economy
    only — premium fills in on the next weekly run or a manual refresh. The
    job runs once and removes itself; `replace_existing=True` means rapid
    trip creations don't queue redundant runs.
    """
    from datetime import datetime, timedelta

    from apscheduler.triggers.date import DateTrigger

    scheduler.add_job(
        _run_collection,
        trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=5)),
        id="early_collection",
        name="One-off collection after trip creation",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("early_collection_scheduled")


def trigger_manual_refresh() -> None:
    """Schedule an immediate one-off full refresh (all fare classes).

    Backs the dashboard's refresh button. Costs 4 searches per date
    (economy + 3 premium classes) — fine for a deliberate button press.
    """
    from datetime import datetime, timedelta

    from apscheduler.triggers.date import DateTrigger

    scheduler.add_job(
        _run_full_collection,
        trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=5)),
        id="manual_refresh",
        name="Manual full refresh (all fare classes)",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("manual_refresh_scheduled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing startup and shutdown events."""
    validate_config()
    logger.info("Flight Deal Tracker starting up")

    # Initialize database tables
    from app.database import create_tables

    await create_tables()
    logger.info("Database tables initialized")

    # Configure and start the scheduler.
    # All recurring jobs use fixed cron times, never intervals: an
    # IntervalTrigger schedules its first firing a full period after startup,
    # so frequent restarts can starve the job forever.
    settings = Settings()

    from apscheduler.triggers.cron import CronTrigger as _CronTrigger
    from apscheduler.triggers.date import DateTrigger as _DateTrigger
    from datetime import datetime as _dt, timedelta as _td

    from sqlalchemy import func, select as _select

    from app.database import async_session_factory as _asf
    from app.models import PriceSnapshot as _PS

    # Daily economy collection. Fares change continuously through the day,
    # so one snapshot per day tracks the trend at a fraction of the API cost;
    # the default hour lands after overnight repricing and before the digest.
    scheduler.add_job(
        _run_collection,
        trigger=_CronTrigger(hour=settings.collection_hour_utc, minute=0),
        id="price_collection",
        name="Daily price collection (main cabin)",
        replace_existing=True,
        max_instances=1,
    )

    # Weekly premium collection — premium fares move slowly and cost 3x.
    scheduler.add_job(
        _run_premium_collection,
        trigger=_CronTrigger(
            day_of_week=settings.premium_collection_weekday,
            hour=settings.premium_collection_hour_utc,
            minute=30,
        ),
        id="premium_price_collection",
        name="Weekly premium fare collection (business, first, premium economy)",
        replace_existing=True,
        max_instances=1,
    )

    # Startup catch-ups: if the app was down (or restarts starved the old
    # interval triggers) past a cadence period, run one-off collections soon
    # after boot instead of waiting for the next cron firing.
    async with _asf() as _session:
        _last_economy = (
            await _session.execute(
                _select(func.max(_PS.collected_at)).where(_PS.fare_class == "main_cabin")
            )
        ).scalar()
        _last_premium = (
            await _session.execute(
                _select(func.max(_PS.collected_at)).where(_PS.fare_class != "main_cabin")
            )
        ).scalar()

    if _last_economy is None or _dt.utcnow() - _last_economy > _td(hours=26):
        scheduler.add_job(
            _run_collection,
            trigger=_DateTrigger(run_date=_dt.now() + _td(seconds=60)),
            id="economy_catchup",
            name="One-off economy catch-up (stale data at startup)",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("economy_catchup_scheduled", last_economy=str(_last_economy))

    if _last_premium is None or _dt.utcnow() - _last_premium > _td(days=8):
        scheduler.add_job(
            _run_premium_collection,
            trigger=_DateTrigger(run_date=_dt.now() + _td(seconds=120)),
            id="premium_catchup",
            name="One-off premium fare catch-up (stale data at startup)",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("premium_catchup_scheduled", last_premium=str(_last_premium))
    if settings.digest_enabled:
        from apscheduler.triggers.cron import CronTrigger
        scheduler.add_job(
            _run_daily_digest,
            trigger=CronTrigger(hour=settings.digest_hour_utc, minute=0),
            id="daily_digest",
            name="Daily flight digest email",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("daily_digest_scheduled", hour_utc=settings.digest_hour_utc)
    # Fixed daily time + a run shortly after startup (maintenance is cheap
    # and idempotent) — an interval trigger would never fire if the app
    # restarts within 24h.
    scheduler.add_job(
        _run_maintenance,
        trigger=_CronTrigger(hour=10, minute=0),
        id="daily_maintenance",
        name="Daily maintenance (expire trips, prune snapshots)",
        replace_existing=True,
        max_instances=1,
    )
    from apscheduler.triggers.date import DateTrigger as _StartupDateTrigger

    scheduler.add_job(
        _run_maintenance,
        trigger=_StartupDateTrigger(run_date=_dt.now() + _td(seconds=30)),
        id="startup_maintenance",
        name="Maintenance catch-up at startup",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _check_collection_staleness,
        trigger=_CronTrigger(hour="*/6", minute=45),
        id="staleness_check",
        name="Alert when price collection goes stale",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Scheduler started",
        collection_hour_utc=settings.collection_hour_utc,
        premium_weekday=settings.premium_collection_weekday,
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
        checks["searchapi"] = "configured" if settings.searchapi_key else "not configured"
        checks["travelpayouts"] = "configured" if settings.travelpayouts_token else "not configured"
        checks["llm"] = "configured" if settings.llm_api_key else "not configured"
    except Exception:
        checks["config"] = "error"

    # Collection freshness
    try:
        from datetime import datetime

        from sqlalchemy import func

        from app.models import Route

        async with async_session_factory() as session:
            last_collected = (
                await session.execute(select(func.max(Route.last_collected_at)))
            ).scalar()
        if last_collected:
            age_hours = (datetime.utcnow() - last_collected).total_seconds() / 3600
            checks["last_collection"] = last_collected.isoformat()
            checks["collection_stale"] = age_hours > 30  # daily cadence + slack
        else:
            checks["last_collection"] = None
            checks["collection_stale"] = False
    except Exception:
        checks["last_collection"] = "error"

    # API quota usage this month
    try:
        from datetime import datetime as _dt

        from app.models import ApiUsage

        month = _dt.utcnow().strftime("%Y-%m")
        async with async_session_factory() as session:
            result = await session.execute(
                select(ApiUsage).where(ApiUsage.month == month)
            )
            checks["api_usage_this_month"] = {
                u.source: u.calls for u in result.scalars().all()
            }
    except Exception:
        checks["api_usage_this_month"] = "error"

    overall = "ok" if checks.get("database") == "ok" and checks.get("scheduler") == "running" else "degraded"
    return {"status": overall, "checks": checks}
