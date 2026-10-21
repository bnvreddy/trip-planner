from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from app.db.database import Base
from datetime import datetime


class DistanceCache(Base):
    __tablename__ = "distance_cache"
    id = Column(String, primary_key=True)  # e.g., "placeA_placeB_driving"
    origin_place_id = Column(String, ForeignKey("locations.place_id"))
    destination_place_id = Column(String, ForeignKey("locations.place_id"))
    travel_mode = Column(String, default="driving")
    duration_minutes = Column(Integer)  # Travel time in minutes
    distance_meters = Column(Integer)   # Distance in meters
    fetched_at = Column(DateTime, default=datetime.utcnow)


class RouteCache(Base):
    """Road geometry for one day's ordered stops (OSRM), so the public demo
    server is hit once per itinerary version rather than once per page view."""
    __tablename__ = "route_cache"
    id = Column(String, primary_key=True)  # sha1 of ordered coords + mode
    travel_mode = Column(String, default="driving")
    distance_meters = Column(Integer)
    duration_minutes = Column(Integer)
    # GeoJSON LineString coordinates, stored as text: [[lng, lat], ...]
    geometry = Column(Text)
    fetched_at = Column(DateTime, default=datetime.utcnow)
