"""Test harness: a throwaway database, fake Google/Gemini/OSRM, real SQL.

Nothing here ever touches the development database. Handlers are exercised
directly (Starlette's TestClient is pinned out by google-genai's httpx
requirement), so these tests cover the same code the HTTP routes call.
"""

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base
import app.models  # noqa: F401  -- registers every table on Base.metadata

TEST_DATABASE = "trip_planner_test"
CITY = "Testville"


def _urls():
    base = make_url(settings.DATABASE_URL)
    return base.set(database="postgres"), base.set(database=TEST_DATABASE)


@pytest.fixture(scope="session")
def engine():
    admin_url, test_url = _urls()

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("""
            SELECT pg_terminate_backend(pid) FROM pg_stat_activity
            WHERE datname = :name AND pid <> pg_backend_pid()
        """), {"name": TEST_DATABASE})
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DATABASE}"))
    admin.dispose()

    test_engine = create_engine(test_url)
    with test_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    Base.metadata.create_all(test_engine)

    yield test_engine

    test_engine.dispose()


PLACES = [
    # (name, category, slot, open, close, visit_minutes, lat, lng, rating)
    ("Test Temple One", "hindu_temple", "morning", "06:00", "12:00", 60, 16.510, 80.610, 4.6),
    ("Test Temple Two", "hindu_temple", "morning", "06:00", "12:00", 60, 16.512, 80.612, 4.5),
    ("Test Museum", "museum", "midday", "10:00", "17:00", 120, 16.514, 80.614, 4.4),
    ("Test Park One", "park", "evening", "09:00", "18:00", 90, 16.516, 80.616, 4.7),
    ("Test Park Two", "park", "evening", "09:00", "18:00", 90, 16.518, 80.618, 4.3),
    ("Test Beach", "beach", "evening", "09:00", "18:00", 90, 16.520, 80.620, 4.8),
    ("Test Temple Three", "hindu_temple", "morning", "06:00", "12:00", 60, 16.522, 80.622, 4.2),
    ("Test Gallery", "art_gallery", "midday", "10:00", "17:00", 90, 16.524, 80.624, 4.1),
    ("Test Garden", "botanical_garden", "evening", "09:00", "18:00", 90, 16.526, 80.626, 4.0),
    ("Test Attraction", "tourist_attraction", "flexible", "09:00", "18:00", 60, 16.528, 80.628, 4.3),
    ("Test Lookout", "viewpoint", "evening", "09:00", "18:00", 45, 16.530, 80.630, 4.4),
    ("Test Lake", "park", "evening", "09:00", "18:00", 60, 16.532, 80.632, 4.2),
]


@pytest.fixture(scope="session")
def seed(engine):
    Session = sessionmaker(bind=engine)
    with Session() as db:
        for index, (name, category, slot, open_at, close_at, minutes, lat, lng, rating) in enumerate(PLACES):
            db.execute(text("""
                INSERT INTO locations
                    (place_id, name, city, geom, weather_dependency, operating_hours,
                     visit_duration, rating, user_ratings_total, primary_category,
                     category_tags, photo_url, time_slot)
                VALUES
                    (:pid, :name, :city, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                     'Mixed', :hours, :minutes, :rating, 500, :category, :tags, NULL, :slot)
            """), {
                "pid": f"test-place-{index}",
                "name": name,
                "city": CITY,
                "lng": lng,
                "lat": lat,
                "hours": json.dumps({"open": open_at, "close": close_at}),
                "minutes": minutes,
                "rating": rating,
                "category": category,
                "tags": json.dumps([category]),
                "slot": slot,
            })
        db.commit()
    return PLACES


def _fake_curate(selected_keywords, candidates, days_count):
    """Deterministic grouping that mixes slots, so days are realistic."""
    by_slot = {}
    for candidate in candidates:
        by_slot.setdefault(candidate.get("slot") or "flexible", []).append(candidate["place_id"])

    ordered = []
    for slot in ("morning", "midday", "evening", "flexible"):
        ordered.extend(by_slot.get(slot, []))

    grouped = {f"day_{day}": [] for day in range(1, days_count + 1)}
    for index, place_id in enumerate(ordered):
        grouped[f"day_{(index % days_count) + 1}"].append(place_id)
    return grouped


def _fake_notes_removed():
    """Placeholder kept out of the way; guide notes were retired."""
    return None


def _fake_plan(locations, durations, day_start, day_end, city=None, mode="driving", allow_llm=True):
    """Tests use the deterministic calculator instead of calling Gemini."""
    from app.services.planning_service import sequence_by_band

    schedule, unplaced = sequence_by_band(locations, durations, day_start, day_end, mode)
    return {"scheduled": schedule, "unplaced": unplaced, "source": "calculator", "problems": []}


@pytest.fixture
def db(engine, seed, monkeypatch):
    from app.api.v1 import trips as trips_module

    monkeypatch.setattr(trips_module, "fetch_and_cache_places_from_google", lambda *a, **k: None)
    monkeypatch.setattr(trips_module, "dedupe_city", lambda session, city: 0)
    monkeypatch.setattr(trips_module, "classify_city_slots", lambda session, city, batch_size=40: 0)
    monkeypatch.setattr(trips_module, "classify_city_durations", lambda session, city, batch_size=40: 0)
    monkeypatch.setattr(trips_module, "curate_and_group_places_with_llm", _fake_curate)
    monkeypatch.setattr(trips_module, "llm_plan_day", _fake_plan)
    monkeypatch.setattr(
        trips_module,
        "get_day_route",
        lambda points, mode, session: {
            "coordinates": [], "distance_meters": 0, "duration_minutes": 0, "source": "unavailable"
        },
    )
    monkeypatch.setattr(
        trips_module,
        "choose_replacement",
        lambda city, removed_name, candidates, keywords=None: (candidates[0], "nearest same-category option"),
    )

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def trip(db):
    """A freshly generated 2-day trip in Testville."""
    from app.api.v1.trips import generate_trip
    from app.schemas.trip_schema import TripRequest

    start = date(2026, 11, 2)
    payload = TripRequest(
        user_id="123e4567-e89b-12d3-a456-426614174000",
        destination_city=CITY,
        start_date=start.isoformat(),
        end_date=(start + timedelta(days=1)).isoformat(),
        transport_mode="Driving",
        selected_keywords=[],
        daily_start_time="09:00",
        daily_end_time="18:00",
    )
    return generate_trip(payload, db)
