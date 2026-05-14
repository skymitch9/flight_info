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

    # LLM
    llm_api_key: str
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"

    # Airline Tiers
    primary_airlines: str = "DL"
    secondary_airlines: str = "AA,UA,WN"
    secondary_threshold: float = 0.15
    tertiary_threshold: float = 0.30
    premium_highlight_threshold: float = 0.40

    # Scheduler
    collection_interval_hours: int = 6

    # Amadeus Flight API
    amadeus_api_key: str = ""
    amadeus_api_secret: str = ""
    amadeus_production: bool = False

    # SerpAPI (Google Flights)
    serpapi_key: str = ""

    class Config:
        env_file = ".env"
