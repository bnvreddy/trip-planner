from app.db.database import engine, Base
from app.models import User, Location, Trip, ItineraryStop # Import all models

Base.metadata.create_all(bind=engine)