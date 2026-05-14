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

    async def notify_if_appropriate(
        self,
        trip: TripRequest,
        analysis: AnalysisResult,
        prices: list[FlightPrice],
    ) -> None:
        """Send a notification if the recommendation warrants it and not throttled.

        Steps:
        1. Skip if recommendation is WAIT
        2. Check 24-hour throttle against last notification time
        3. Filter main cabin options via TierEngine
        4. Identify premium highlights via TierEngine
        5. Format email using Jinja2 template
        6. Send with retry (3 attempts, exponential backoff)
        7. Record notification in DB

        Args:
            trip: The TripRequest that was analyzed.
            analysis: The AnalysisResult with the recommendation.
            prices: All collected flight prices for this trip.
        """
        # 1. Skip if recommendation is WAIT
        if analysis.recommendation == Recommendation.WAIT.value:
            logger.info(
                "Skipping notification: recommendation is WAIT",
                trip_id=trip.id,
            )
            return

        async with self.session_factory() as session:
            # 2. Check 24-hour throttle
            if await self._is_throttled(session, trip.id):
                logger.info(
                    "Skipping notification: throttled (within 24 hours)",
                    trip_id=trip.id,
                )
                return

            # 3. Filter main cabin options via TierEngine
            main_cabin_prices = [
                p for p in prices if p.fare_class == "main_cabin"
            ]
            main_cabin_options = self.tier_engine.filter_options(main_cabin_prices)

            # 4. Identify premium highlights
            premium_highlights = self.tier_engine.identify_premium_highlights(prices)

            # 5. Format email
            subject, body = self._format_email(
                trip, analysis, main_cabin_options, premium_highlights
            )

            # 6. Send with retry
            success = await self._send_with_retry(subject, body)

            # 7. Record notification in DB
            status = "sent" if success else "failed"
            notification = Notification(
                trip_request_id=trip.id,
                sent_at=datetime.utcnow(),
                status=status,
            )
            session.add(notification)
            await session.commit()

            logger.info(
                "Notification recorded",
                trip_id=trip.id,
                status=status,
            )

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

    def _format_email(
        self,
        trip: TripRequest,
        analysis: AnalysisResult,
        main_cabin_options: list[FlightPrice],
        premium_highlights: list[FlightPrice],
    ) -> tuple[str, str]:
        """Format the notification email using a Jinja2 template.

        Args:
            trip: The TripRequest being notified about.
            analysis: The AnalysisResult with recommendation and explanation.
            main_cabin_options: Filtered main cabin flight options (up to 3).
            premium_highlights: Premium fare highlights within threshold.

        Returns:
            A tuple of (subject, html_body) for the email.
        """
        subject = (
            f"Flight Deal Alert: {trip.origin} → {trip.destination} "
            f"— {analysis.recommendation.replace('_', ' ').title()}"
        )

        template = self._jinja_env.get_template("deal_notification.html")
        body = template.render(
            trip=trip,
            analysis=analysis,
            main_cabin_options=main_cabin_options,
            premium_highlights=premium_highlights,
        )

        return subject, body

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
