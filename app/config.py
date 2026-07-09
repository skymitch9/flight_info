from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str

    # Email
    smtp_host: str
    smtp_port: int = 465
    smtp_username: str
    smtp_password: str
    notification_email: str

    # Daily Digest
    digest_enabled: bool = True
    digest_hour_utc: int = 17  # 10 AM Arizona (UTC-7) = 17 UTC
    digest_result_count: int = 3
    digest_required_airlines: str = "DL"  # comma-separated, at least one must appear
    digest_no_same_airline: bool = True  # results can't all be the same airline

    # LLM (Anthropic Claude — LLMClient speaks the Anthropic Messages API)
    llm_api_key: str
    llm_model: str = "claude-sonnet-4-6"
    llm_base_url: str = "https://api.anthropic.com/v1"

    # Airline Tiers
    primary_airlines: str = "DL"
    secondary_airlines: str = "AA,UA,WN"
    secondary_threshold: float = 0.15
    tertiary_threshold: float = 0.30
    premium_highlight_threshold: float = 0.40

    # Scheduler — daily cadence. Fare changes flow continuously (no magic
    # hour), so intra-day polling mostly re-reads the same prices; one
    # snapshot per day captures the trend at a quarter of the API cost.
    # 13:00 UTC = 6 AM Arizona — after overnight/evening repricing, ahead
    # of the morning digest.
    collection_hour_utc: int = 13
    # Premium fares (premium economy/business/first) change slowly and cost
    # 3 searches per date — collect weekly. Cron day-of-week string
    # ("tue", "mon,thu", ...), fixed times so restarts can't starve the job.
    premium_collection_weekday: str = "tue"
    premium_collection_hour_utc: int = 13
    # Close-in boost: trips departing within this many days get a second
    # daily economy collection (prices move fast near departure). Runs at
    # closein_collection_hour_utc (default 01:00 UTC = 6 PM Arizona, the
    # evening-repricing window). Costs nothing while no trip is close-in.
    closein_window_days: int = 14
    closein_collection_hour_utc: int = 1

    # Suppress repeat alerts unless the cheapest qualifying fare moved by at
    # least this fraction since the last alert (target hits included)
    alert_min_change_pct: float = 0.05

    # Nightly pg_dump into db-snapshots/ (mounted at /backups in the container)
    backup_enabled: bool = True
    backup_retention_count: int = 7

    # Collection date sampling — bounds API quota usage per cycle.
    # Each trip contributes up to max_dates_per_trip evenly spaced dates from
    # its travel window; each route searches at most max_search_dates_per_route.
    max_dates_per_trip: int = 3
    max_search_dates_per_route: int = 6

    # Airlines only publish fares ~330 days ahead. Dates beyond this horizon
    # are not searched; trips further out can still be created ("prepared")
    # and collection starts automatically once their window comes in range.
    booking_horizon_days: int = 330

    # Amadeus Flight API
    amadeus_api_key: str = ""
    amadeus_api_secret: str = ""
    amadeus_production: bool = False

    # SerpAPI (Google Flights) — primary source
    serpapi_key: str = ""

    # SearchAPI.io (Google Flights) — fallback source
    searchapi_key: str = ""

    # Travelpayouts / Aviasales cached prices — free fallback source
    travelpayouts_token: str = ""

    # Monthly API budgets (searches per calendar month; 0 = unlimited).
    # When a source hits its budget it is skipped and the next fallback
    # source is used instead.
    serpapi_monthly_budget: int = 250
    searchapi_monthly_budget: int = 100
    amadeus_monthly_budget: int = 2000

    # Delete price snapshots older than this many days (0 disables pruning)
    snapshot_retention_days: int = 180

    class Config:
        env_file = ".env"
