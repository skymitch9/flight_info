"""Shared helper for recording external API usage in the api_usage table."""

from datetime import datetime

import structlog
from sqlalchemy import select

from app.models import ApiUsage

logger = structlog.get_logger(__name__)


async def record_api_usage(session_factory, source: str, count: int = 1) -> None:
    """Increment the per-month call counter for an external API source.

    Best-effort: failures are logged, never raised — metering must not break
    the operation being metered.
    """
    month = datetime.utcnow().strftime("%Y-%m")
    try:
        async with session_factory() as session:
            result = await session.execute(
                select(ApiUsage).where(ApiUsage.source == source, ApiUsage.month == month)
            )
            usage = result.scalar_one_or_none()
            if usage is None:
                usage = ApiUsage(source=source, month=month, calls=0)
                session.add(usage)
            usage.calls += count
            await session.commit()
    except Exception as exc:
        logger.warning("api_usage_record_failed", source=source, error=str(exc))
