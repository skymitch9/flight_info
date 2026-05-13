from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


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
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    price_snapshots = relationship("PriceSnapshot", back_populates="trip_request")
    analysis_results = relationship("AnalysisResult", back_populates="trip_request")
    notifications = relationship("Notification", back_populates="trip_request")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True)
    trip_request_id = Column(Integer, ForeignKey("trip_requests.id"), nullable=False)
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

    trip_request = relationship("TripRequest", back_populates="price_snapshots")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True)
    trip_request_id = Column(Integer, ForeignKey("trip_requests.id"), nullable=False)
    recommendation = Column(String(20), nullable=False)
    explanation = Column(Text, nullable=False)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    trip_request = relationship("TripRequest", back_populates="analysis_results")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    trip_request_id = Column(Integer, ForeignKey("trip_requests.id"), nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(10), nullable=False)  # "sent" | "failed"

    trip_request = relationship("TripRequest", back_populates="notifications")
