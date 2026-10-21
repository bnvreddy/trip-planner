from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, Date, Time
from sqlalchemy.dialects.postgresql import JSONB
from app.db.database import Base


class Trip(Base):
    __tablename__ = "trips"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    city = Column(String, nullable=False)
    days_count = Column(Integer, default=1)
    created_at = Column(DateTime)
    start_date = Column(Date)
    end_date = Column(Date)
    transport_mode = Column(String, default="driving")
    # The planning window the user picked. Persisted so every re-optimization
    # (move / reorder / recalculate / extend) reuses it instead of silently
    # falling back to 09:00-18:00.
    day_start_time = Column(Time)
    day_end_time = Column(Time)
    # Per-day overrides: [{"start": "09:00", "end": "13:00"}, ...]. NULL or a
    # missing entry falls back to the trip-level window above.
    day_windows = Column(JSONB)
    updated_at = Column(DateTime)


class ItineraryStop(Base):
    __tablename__ = "itinerary_stops"
    id = Column(String, primary_key=True)
    trip_id = Column(String, ForeignKey("trips.id"))
    place_id = Column(String, ForeignKey("locations.place_id"))
    day_number = Column(Integer, default=1)
    scheduled_start = Column(DateTime)
    scheduled_end = Column(DateTime)
    status = Column(String, default="PENDING")
    is_locked = Column(Boolean, default=False)
    guide_note = Column(Text, nullable=True)
    # Per-stop override ("I want to stay an hour longer").
    # NULL means: use locations.visit_duration.
    duration_minutes = Column(Integer, nullable=True)
