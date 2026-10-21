"""Idempotent schema migration.

``Base.metadata.create_all`` creates missing tables but never alters existing
ones, so every column added after the first deploy has to be applied here.
Every statement is safe to run repeatedly.

Run from the backend directory::

    python -m app.db.migrate
"""

from sqlalchemy import text

from app.db.database import engine

# New columns on tables that already exist in deployed databases.
ALTERATIONS = [
    "ALTER TABLE trips ADD COLUMN IF NOT EXISTS day_start_time TIME",
    "ALTER TABLE trips ADD COLUMN IF NOT EXISTS day_end_time TIME",
    "ALTER TABLE trips ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
    "ALTER TABLE itinerary_stops ADD COLUMN IF NOT EXISTS duration_minutes INTEGER",
    "ALTER TABLE locations ADD COLUMN IF NOT EXISTS time_slot TEXT",
    "ALTER TABLE locations ADD COLUMN IF NOT EXISTS duration_source TEXT",
    "ALTER TABLE locations ADD COLUMN IF NOT EXISTS hours_source TEXT",
    "ALTER TABLE trips ADD COLUMN IF NOT EXISTS day_windows JSONB",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT",
]

# Tables introduced later than the initial schema (create_all would handle these,
# but migrate has to stand on its own).
CREATIONS = [
    """
    CREATE TABLE IF NOT EXISTS route_cache (
        id TEXT PRIMARY KEY,
        travel_mode TEXT,
        distance_meters INTEGER,
        duration_minutes INTEGER,
        geometry TEXT,
        fetched_at TIMESTAMP DEFAULT NOW()
    )
    """,
]

# Fill the new columns for rows that predate them.
BACKFILLS = [
    ("trips.day_start_time", "UPDATE trips SET day_start_time = TIME '09:00' WHERE day_start_time IS NULL"),
    ("trips.day_end_time", "UPDATE trips SET day_end_time = TIME '18:00' WHERE day_end_time IS NULL"),
    ("trips.updated_at", "UPDATE trips SET updated_at = COALESCE(created_at, NOW()) WHERE updated_at IS NULL"),
    ("locations.duration_source",
     "UPDATE locations SET duration_source = 'default' WHERE duration_source IS NULL"),
    ("locations.hours_source",
     "UPDATE locations SET hours_source = 'assumed' WHERE hours_source IS NULL"),
]


def ensure_schema() -> None:
    """Apply the additive changes quietly.

    Called at application startup: a running server must never be one migration
    behind its own models (that mismatch surfaced as a 500 on /trips/generate).
    """
    with engine.begin() as conn:
        for statement in CREATIONS:
            conn.execute(text(statement))
        for statement in ALTERATIONS:
            conn.execute(text(statement))
        for _label, statement in BACKFILLS:
            conn.execute(text(statement))


def run() -> None:
    applied = []
    with engine.begin() as conn:
        for statement in CREATIONS:
            conn.execute(text(statement))
        for statement in ALTERATIONS:
            conn.execute(text(statement))
        for label, statement in BACKFILLS:
            changed = conn.execute(text(statement)).rowcount
            applied.append(f"{label}: {changed} row(s) backfilled")
    print("Migration applied (idempotent):")
    for line in applied:
        print("  -", line)


if __name__ == "__main__":
    run()
