from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    status = Column(String(10), nullable=False, default="active")  # "active" | "dormant"
    last_collected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("origin", "destination", name="uq_route_origin_dest"),)

    price_snapshots = relationship("PriceSnapshot", back_populates="route")
    trip_requests = relationship("TripRequest", back_populates="route")


class TripRequest(Base):
    __tablename__ = "trip_requests"

    id = Column(Integer, primary_key=True)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    earliest_departure = Column(Date, nullable=False)
    latest_departure = Column(Date, nullable=False)
    earliest_return = Column(Date, nullable=True)
    latest_return = Column(Date, nullable=True)
    latest_departure_time = Column(String(5), nullable=True)  # "HH:MM" - latest time willing to depart
    latest_return_time = Column(String(5), nullable=True)  # "HH:MM" - latest time willing to return
    passenger_count = Column(Integer, nullable=False, default=1)
    carry_on_bags = Column(Integer, nullable=False, default=1)
    checked_bags = Column(Integer, nullable=False, default=0)
    # Alert when the cheapest main-cabin fare (per ticket; round-trip
    # combined when return dates are set) drops to/below this
    target_price_cents = Column(Integer, nullable=True)
    # Only consider fares with at most this many stops (NULL = any)
    max_stops = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)  # nullable during migration, enforced after
    status = Column(String(10), nullable=False, default="active")  # "active" | "fulfilled"
    fulfilled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("passenger_count BETWEEN 1 AND 9", name="chk_passenger_count_range"),
        CheckConstraint("carry_on_bags BETWEEN 0 AND 2", name="chk_carry_on_bags_range"),
        CheckConstraint("checked_bags BETWEEN 0 AND 5", name="chk_checked_bags_range"),
    )

    route = relationship("Route", back_populates="trip_requests")
    price_snapshots = relationship("PriceSnapshot", back_populates="trip_request")
    analysis_results = relationship("AnalysisResult", back_populates="trip_request")
    notifications = relationship("Notification", back_populates="trip_request")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True)
    trip_request_id = Column(Integer, ForeignKey("trip_requests.id"), nullable=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)  # nullable during migration
    airline_code = Column(String(3), nullable=False)
    flight_number = Column(String(10), nullable=False)
    departure_time = Column(String(25), nullable=False)
    arrival_time = Column(String(25), nullable=False)
    fare_class = Column(String(20), nullable=False)
    price_cents = Column(Integer, nullable=False)
    flight_date = Column(Date, nullable=False)
    stops = Column(Integer, default=0)
    total_duration_minutes = Column(Integer, default=0)
    segments_json = Column(Text, nullable=True)  # JSON array of segment details
    collected_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_price_snapshots_route_collected", "route_id", "collected_at"),
        Index("ix_price_snapshots_trip_request_id", "trip_request_id"),
        Index("ix_price_snapshots_flight_date", "flight_date"),
    )

    trip_request = relationship("TripRequest", back_populates="price_snapshots")
    route = relationship("Route", back_populates="price_snapshots")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True)
    trip_request_id = Column(Integer, ForeignKey("trip_requests.id"), nullable=False)
    recommendation = Column(String(20), nullable=False)
    explanation = Column(Text, nullable=False)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_analysis_results_trip_analyzed", "trip_request_id", "analyzed_at"),
    )

    trip_request = relationship("TripRequest", back_populates="analysis_results")


class ApiUsage(Base):
    """Per-source, per-calendar-month count of external API searches.

    Backs the quota budget guard: sources whose count reaches their monthly
    budget are skipped for the rest of the month.
    """

    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)
    month = Column(String(7), nullable=False)  # "YYYY-MM"
    calls = Column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("source", "month", name="uq_api_usage_source_month"),)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    trip_request_id = Column(Integer, ForeignKey("trip_requests.id"), nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(10), nullable=False)  # "sent" | "failed"
    # Cheapest qualifying fare at alert time — used to suppress repeat
    # alerts when the price hasn't meaningfully changed
    min_price_cents = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_notifications_trip_sent", "trip_request_id", "sent_at"),
    )

    trip_request = relationship("TripRequest", back_populates="notifications")
