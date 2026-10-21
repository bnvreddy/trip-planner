from sqlalchemy import Column, String, Integer, Float, JSON
from geoalchemy2 import Geometry
from app.db.database import Base

class Location(Base):
    __tablename__ = "locations"
    place_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    geom = Column(Geometry('POINT', srid=4326))
    weather_dependency = Column(String)
    operating_hours = Column(JSON)
    visit_duration = Column(Integer, default=90)
    rating = Column(Float, default=0.0)
    user_ratings_total = Column(Integer, default=0)
    primary_category = Column(String)
    category_tags = Column(JSON, default=[])
    photo_url = Column(String, nullable=True)
    # Preferred part of the day (morning/midday/afternoon/evening/flexible).
    time_slot = Column(String, nullable=True)
    # "llm" | "rule" | "default" -- how visit_duration was decided.
    duration_source = Column(String, nullable=True)
    # "google" | "assumed" -- assumed means the 09:00-18:00 placeholder, which
    # must not be allowed to constrain a schedule.
    hours_source = Column(String, nullable=True)