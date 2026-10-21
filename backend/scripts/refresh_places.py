"""Rebuild the place catalogue for one or more cities.

Fetches places from Google, merges near-duplicates, then classifies the
time-of-day slot and the visit duration for anything new.

    python -m scripts.refresh_places
    python -m scripts.refresh_places --city Vizag
"""

import sys

from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.duration_service import classify_city_durations
from app.services.place_hygiene import dedupe_city
from app.services.places_service import fetch_and_cache_places_from_google
from app.services.slot_service import classify_city_slots

DEFAULT_CITIES = ["Vizag", "Vijayawada"]


def main(cities, force=False):
    with SessionLocal() as db:
        for city in cities:
            print(f"\n=== {city} ===")
            existing = db.execute(
                text("SELECT COUNT(*) FROM locations WHERE city = :city"), {"city": city}
            ).scalar()

            if existing and not force:
                print(f"  {existing} places already stored -- reusing them (use --force to refetch)")
            else:
                fetch_and_cache_places_from_google(city, [], db)

            merged = dedupe_city(db, city)
            if merged:
                print(f"  merged {merged} near-duplicate place(s)")

            slots = classify_city_slots(db, city)
            durations = classify_city_durations(db, city)
            total = db.execute(
                text("SELECT COUNT(*) FROM locations WHERE city = :city"), {"city": city}
            ).scalar()
            print(f"  {total} places · {slots} slots classified · {durations} durations classified")

        print("\nCatalogue summary:")
        for row in db.execute(text("""
            SELECT city, COUNT(*) AS n,
                   COUNT(*) FILTER (WHERE time_slot IS NOT NULL) AS slotted,
                   ROUND(AVG(visit_duration)) AS avg_minutes
            FROM locations GROUP BY city ORDER BY city
        """)).fetchall():
            print(f"  {row.city}: {row.n} places, {row.slotted} with a slot, avg {row.avg_minutes} min")


if __name__ == "__main__":
    force = "--force" in sys.argv
    if "--city" in sys.argv:
        main([sys.argv[sys.argv.index("--city") + 1]], force)
    else:
        main(DEFAULT_CITIES, force)
