"""Delete the throwaway trips created while testing.

Read-only unless ``--apply`` is passed. Places and the distance cache are kept.

    python -m scripts.purge_trips            # what would be deleted
    python -m scripts.purge_trips --apply    # actually delete
"""

import sys

from sqlalchemy import text

from app.db.database import engine


def main(apply: bool = False):
    with engine.begin() as conn:
        trips = conn.execute(text("""
            SELECT id, city, days_count, start_date,
                   (SELECT COUNT(*) FROM itinerary_stops s WHERE s.trip_id = t.id) AS stops
            FROM trips t
            ORDER BY start_date
        """)).fetchall()

        total_stops = sum(row.stops for row in trips)
        print(f"{len(trips)} trip(s), {total_stops} stop(s):")
        for row in trips:
            print(f"  - {row.city}  {row.start_date}  {row.days_count} days  {row.stops} stops")

        if not apply:
            print("\nDry run. Re-run with --apply to delete.")
            return

        conn.execute(text("DELETE FROM itinerary_stops"))
        conn.execute(text("DELETE FROM trips"))

        remaining = conn.execute(text("SELECT COUNT(*) FROM trips")).scalar()
        places = conn.execute(text("SELECT COUNT(*) FROM locations")).scalar()
        legs = conn.execute(text("SELECT COUNT(*) FROM distance_cache")).scalar()
        print(f"\nDeleted. trips={remaining}, places kept={places}, cached legs kept={legs}")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
