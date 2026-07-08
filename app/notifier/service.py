"""Email notification service with throttling and retry logic.

Sends Deal_Notification emails when the price analysis recommends action,
respecting a 24-hour throttle per trip to avoid notification fatigue.
"""

import asyncio
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analyzer.service import Recommendation
from app.collector.base import FlightPrice
from app.config import Settings
from app.models import AnalysisResult, Notification, TripRequest
from app.tiers.engine import TierEngine

logger = structlog.get_logger(__name__)

# Path to email templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"


class NotificationService:
    """Handles Deal_Notification delivery with throttling and retry.

    Checks whether a notification is warranted (non-WAIT recommendation,
    not throttled), filters flight options via the TierEngine, formats
    the email using a Jinja2 template, and sends with retry logic.
    """

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        tier_engine: TierEngine,
    ):
        """Initialize the NotificationService.

        Args:
            settings: Application settings containing SMTP configuration.
            session_factory: Async session factory for database access.
            tier_engine: TierEngine instance for filtering flight options.
        """
        self.settings = settings
        self.session_factory = session_factory
        self.tier_engine = tier_engine
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )

    async def build_alert(
        self,
        trip: TripRequest,
        analysis: AnalysisResult,
        prices: list[FlightPrice],
        force_reason: str | None = None,
    ) -> dict | None:
        """Build an alert section for a trip, or None if no alert is due.

        An alert is due when the recommendation is not WAIT (or force_reason
        is set, e.g. the trip's target price was hit) and the trip has not
        been notified within the last 24 hours.

        Returns:
            A dict with keys trip/analysis/main_cabin_options/
            premium_highlights/target_note, or None.
        """
        if force_reason is None and analysis.recommendation == Recommendation.WAIT.value:
            logger.info(
                "Skipping notification: recommendation is WAIT",
                trip_id=trip.id,
            )
            return None

        async with self.session_factory() as session:
            if await self._is_throttled(session, trip.id):
                logger.info(
                    "Skipping notification: throttled (within 24 hours)",
                    trip_id=trip.id,
                )
                return None

        main_cabin_prices = [p for p in prices if p.fare_class == "main_cabin"]
        return {
            "trip": trip,
            "analysis": analysis,
            "main_cabin_options": self.tier_engine.filter_options(main_cabin_prices),
            "premium_highlights": self.tier_engine.identify_premium_highlights(prices),
            "target_note": force_reason,
        }

    async def send_alerts(self, alerts: list[dict]) -> None:
        """Send a single combined email covering all due alerts.

        One email per collection cycle regardless of how many trips alert —
        each trip gets its own section. Records a Notification row per trip
        so the 24-hour throttle applies individually.

        Args:
            alerts: Alert dicts produced by build_alert().
        """
        if not alerts:
            return

        subject = self._combined_subject(alerts)
        template = self._jinja_env.get_template("combined_alert.html")
        body = template.render(alerts=alerts)

        success = await self._send_with_retry(subject, body)

        status = "sent" if success else "failed"
        async with self.session_factory() as session:
            for alert in alerts:
                session.add(
                    Notification(
                        trip_request_id=alert["trip"].id,
                        sent_at=datetime.utcnow(),
                        status=status,
                    )
                )
            await session.commit()

        logger.info(
            "Combined notification recorded",
            trips=[a["trip"].id for a in alerts],
            status=status,
        )

    @staticmethod
    def _combined_subject(alerts: list[dict]) -> str:
        """Subject line summarizing all alerting trips."""
        any_target = any(a["target_note"] for a in alerts)
        routes = [f"{a['trip'].origin}→{a['trip'].destination}" for a in alerts]
        shown = ", ".join(routes[:3])
        if len(routes) > 3:
            shown += f" +{len(routes) - 3} more"
        prefix = "Target Price Hit" if any_target else "Flight Deal Alert"
        return f"{prefix}: {shown}"

    async def _is_throttled(self, session: AsyncSession, trip_id: int) -> bool:
        """Check if a notification was sent for this trip within the last 24 hours.

        Args:
            session: The async database session.
            trip_id: The trip request ID to check.

        Returns:
            True if a notification was sent within the last 24 hours.
        """
        cutoff = datetime.utcnow() - timedelta(hours=24)
        stmt = (
            select(Notification)
            .where(Notification.trip_request_id == trip_id)
            .where(Notification.sent_at >= cutoff)
            .where(Notification.status == "sent")
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _send_with_retry(
        self, subject: str, body: str, max_retries: int = 3
    ) -> bool:
        """Send email with exponential backoff retry (1s, 2s, 4s).

        Args:
            subject: The email subject line.
            body: The HTML email body.
            max_retries: Maximum number of send attempts (default 3).

        Returns:
            True if the email was sent successfully, False otherwise.
        """
        for attempt in range(max_retries):
            try:
                await self._send_email(subject, body)
                logger.info("Email sent successfully", attempt=attempt + 1)
                return True
            except Exception as exc:
                wait_time = 2**attempt  # 1s, 2s, 4s
                if attempt < max_retries - 1:
                    logger.warning(
                        "Email send failed, retrying",
                        attempt=attempt + 1,
                        wait_seconds=wait_time,
                        error=str(exc),
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "Failed to send notification after all retries",
                        attempts=max_retries,
                        error=str(exc),
                    )
        return False

    async def _send_email(self, subject: str, body: str) -> None:
        """Send an email via SMTP using aiosmtplib.

        Args:
            subject: The email subject line.
            body: The HTML email body.

        Raises:
            Exception: If the email cannot be sent.
        """
        message = MIMEMultipart("alternative")
        message["From"] = self.settings.smtp_username
        message["To"] = self.settings.notification_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "html"))

        await aiosmtplib.send(
            message,
            hostname=self.settings.smtp_host,
            port=self.settings.smtp_port,
            username=self.settings.smtp_username,
            password=self.settings.smtp_password,
            use_tls=self.settings.smtp_port == 465,
            start_tls=self.settings.smtp_port != 465,
        )
