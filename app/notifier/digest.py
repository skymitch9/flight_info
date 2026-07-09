"""Daily digest email service.

Sends a daily summary email with the top flight options for each active contract,
respecting airline diversity requirements and configurable result counts.
"""

from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import PriceSnapshot, Route, TripRequest
from app.pricing.calculator import LuggageConfig, calculate_total_price

logger = structlog.get_logger(__name__)


class DailyDigestService:
    """Builds and sends a daily digest email with top flights per contract."""

    def __init__(self, settings: Settings, session_factory: async_sessionmaker[AsyncSession]):
        self.settings = settings
        self.session_factory = session_factory
        self.result_count = settings.digest_result_count
        self.required_airlines = [
            a.strip() for a in settings.digest_required_airlines.split(",") if a.strip()
        ]
        self.no_same_airline = settings.digest_no_same_airline

    async def send_daily_digest(self) -> None:
        """Build and send the daily digest email."""
        async with self.session_factory() as session:
            trips = await self._load_active_trips(session)

        if not trips:
            logger.info("daily_digest_skipped", reason="no active trips")
            return

        html = self._build_digest_html(trips)
        subject = f"Flight Tracker Daily Digest — {datetime.utcnow().strftime('%b %d, %Y')}"

        try:
            await self._send_email(subject, html)
            logger.info("daily_digest_sent", trips=len(trips))
        except Exception as exc:
            logger.error("daily_digest_failed", error=str(exc))

    async def _load_active_trips(self, session: AsyncSession) -> list[dict]:
        """Load active trips with their route snapshots."""
        result = await session.execute(
            select(TripRequest)
            .where(TripRequest.is_active == True)  # noqa: E712
            .where(TripRequest.status == "active")
            .options(
                selectinload(TripRequest.route).selectinload(Route.price_snapshots),
                selectinload(TripRequest.analysis_results),
            )
        )
        trips = result.scalars().all()

        from app.analyzer.deal_context import compute_deal_context, describe_deal

        trip_data = []
        for trip in trips:
            snapshots = trip.route.price_snapshots if trip.route else []
            top_flights = self._select_top_flights(snapshots, trip)
            latest_analysis = None
            if trip.analysis_results:
                latest_analysis = max(trip.analysis_results, key=lambda a: a.analyzed_at)

            # Deal context over bookable main-cabin fares in the trip window
            history = [
                s
                for s in snapshots
                if s.fare_class == "main_cabin"
                and trip.earliest_departure <= s.flight_date <= trip.latest_departure
                and (trip.max_stops is None or (s.stops or 0) <= trip.max_stops)
            ]
            deal_note = describe_deal(compute_deal_context(history))

            trip_data.append({
                "trip": trip,
                "top_flights": top_flights,
                "analysis": latest_analysis,
                "deal_note": deal_note,
            })

        return trip_data

    def _select_top_flights(self, snapshots: list[PriceSnapshot], trip: TripRequest) -> list[dict]:
        """Select top N flights respecting airline diversity rules."""
        if not snapshots:
            return []

        from datetime import timedelta

        # Only flights inside this trip's departure window — the route may
        # carry snapshots for other trips' dates and reverse-leg collections
        snapshots = [
            s
            for s in snapshots
            if trip.earliest_departure <= s.flight_date <= trip.latest_departure
        ]

        # Honor the trip's max-stops preference
        if trip.max_stops is not None:
            snapshots = [s for s in snapshots if (s.stops or 0) <= trip.max_stops]

        # Get latest batch per fare class (main_cabin only for digest)
        main_cabin = [s for s in snapshots if s.fare_class == "main_cabin"]
        if not main_cabin:
            main_cabin = snapshots

        # Latest batch
        if main_cabin:
            latest = max(s.collected_at for s in main_cabin)
            cutoff = latest - timedelta(minutes=5)
            batch = [s for s in main_cabin if s.collected_at >= cutoff]
        else:
            batch = []

        # Sort by price
        batch.sort(key=lambda s: s.price_cents)

        luggage = LuggageConfig(carry_on_bags=trip.carry_on_bags, checked_bags=trip.checked_bags)

        # Build candidate list with total prices
        candidates = []
        for snap in batch:
            breakdown = calculate_total_price(snap.price_cents, snap.airline_code, luggage, trip.passenger_count)
            candidates.append({
                "airline": snap.airline_code,
                "flight_number": snap.flight_number,
                "departure_time": snap.departure_time,
                "arrival_time": snap.arrival_time,
                "stops": snap.stops or 0,
                "base_price_cents": snap.price_cents,
                "total_price_cents": breakdown.total_price_cents,
                "flight_date": snap.flight_date,
            })

        # Apply diversity rules
        selected = self._apply_diversity_rules(candidates)
        return selected[:self.result_count]

    def _apply_diversity_rules(self, candidates: list[dict]) -> list[dict]:
        """Apply airline diversity: include required airlines, avoid all-same."""
        if not candidates:
            return []

        selected: list[dict] = []
        used_indices: set[int] = set()

        # First, ensure required airlines are represented
        for req_airline in self.required_airlines:
            for i, c in enumerate(candidates):
                if i not in used_indices and c["airline"] == req_airline:
                    selected.append(c)
                    used_indices.add(i)
                    break

        # Fill remaining slots with cheapest options
        for i, c in enumerate(candidates):
            if len(selected) >= self.result_count:
                break
            if i not in used_indices:
                selected.append(c)
                used_indices.add(i)

        # Check no-same-airline rule
        if self.no_same_airline and len(selected) > 1:
            airlines = set(s["airline"] for s in selected)
            if len(airlines) == 1:
                # Try to swap the last slot with a different airline
                single_airline = next(iter(airlines))
                for i, c in enumerate(candidates):
                    if i not in used_indices and c["airline"] != single_airline:
                        selected[-1] = c
                        break

        # Sort final selection by total price
        selected.sort(key=lambda s: s["total_price_cents"])
        return selected

    def _build_digest_html(self, trips_data: list[dict]) -> str:
        """Build the HTML email body for the daily digest."""
        rows = []
        for td in trips_data:
            trip = td["trip"]
            analysis = td["analysis"]
            flights = td["top_flights"]

            rec = analysis.recommendation.replace("_", " ").upper() if analysis else "NO DATA"
            route = f"{trip.origin} → {trip.destination}"
            dates = f"{trip.earliest_departure.strftime('%b %d')} – {trip.latest_departure.strftime('%b %d')}"

            flight_rows = ""
            for f in flights:
                price = f"${f['total_price_cents'] // 100}"
                base = f"${f['base_price_cents'] // 100}"
                dep = f.get("departure_time", "")[:5] if f.get("departure_time") else ""
                arr = f.get("arrival_time", "")[:5] if f.get("arrival_time") else ""
                stops = "Nonstop" if f["stops"] == 0 else f"{f['stops']} stop{'s' if f['stops'] > 1 else ''}"
                flight_rows += f"""
                <tr style="border-bottom:1px solid #2a2a4a;">
                    <td style="padding:6px 10px;color:#e0e0e0;">{f['airline']} {f['flight_number']}</td>
                    <td style="padding:6px 10px;color:#8888aa;">{dep} – {arr}</td>
                    <td style="padding:6px 10px;color:#8888aa;">{stops}</td>
                    <td style="padding:6px 10px;color:#8888aa;">{base}</td>
                    <td style="padding:6px 10px;color:#00F0FF;font-weight:700;">{price}</td>
                </tr>"""

            rows.append(f"""
            <div style="margin-bottom:24px;border:1px solid #2a2a4a;border-left:3px solid #FCEE09;padding:16px;background:#12121a;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-family:Orbitron,sans-serif;font-size:14px;color:#e0e0e0;letter-spacing:2px;">{route}</span>
                    <span style="font-family:monospace;font-size:11px;color:#00F0FF;border:1px solid #00F0FF;padding:2px 8px;">{rec}</span>
                </div>
                <div style="font-family:monospace;font-size:11px;color:#555577;margin-bottom:10px;">{dates} • {trip.passenger_count} pax • {trip.carry_on_bags} carry-on • {trip.checked_bags} checked{f" • ≤{trip.max_stops} stops" if trip.max_stops is not None else ""}</div>
                {f'<div style="font-family:monospace;font-size:11px;color:#00F0FF;margin-bottom:10px;">📉 {td["deal_note"]}</div>' if td.get("deal_note") else ""}
                <table style="width:100%;border-collapse:collapse;font-size:12px;">
                    <tr style="border-bottom:1px solid #2a2a4a;">
                        <th style="text-align:left;padding:4px 10px;color:#555577;font-size:10px;">FLIGHT</th>
                        <th style="text-align:left;padding:4px 10px;color:#555577;font-size:10px;">TIME</th>
                        <th style="text-align:left;padding:4px 10px;color:#555577;font-size:10px;">STOPS</th>
                        <th style="text-align:left;padding:4px 10px;color:#555577;font-size:10px;">BASE</th>
                        <th style="text-align:left;padding:4px 10px;color:#555577;font-size:10px;">TOTAL</th>
                    </tr>
                    {flight_rows}
                </table>
            </div>""")

        body = f"""
        <div style="background:#0a0a0f;padding:24px;font-family:'Rajdhani',Arial,sans-serif;">
            <h1 style="font-family:Orbitron,sans-serif;color:#FCEE09;font-size:18px;letter-spacing:3px;margin-bottom:4px;">FLIGHT TRACKER DAILY DIGEST</h1>
            <p style="font-family:monospace;font-size:11px;color:#555577;margin-bottom:24px;">{datetime.utcnow().strftime('%B %d, %Y')} • {len(trips_data)} active contracts</p>
            {''.join(rows)}
            <p style="font-family:monospace;font-size:10px;color:#333355;margin-top:24px;border-top:1px solid #1a1a2e;padding-top:12px;">
                Showing top {self.result_count} options per contract (must include: {', '.join(self.required_airlines) or 'any'}) • Prices include bag fees × passengers
            </p>
        </div>
        """
        return body

    async def _send_email(self, subject: str, body: str) -> None:
        """Send the digest email via SMTP."""
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
