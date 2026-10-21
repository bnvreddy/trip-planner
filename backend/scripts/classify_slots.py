"""Classify time-of-day slots for stored places.

One-time (and idempotent) pass: places that already have a slot are skipped.

    python -m scripts.classify_slots
    python -m scripts.classify_slots --city Vizag
"""

import sys

from sqlalchemy import text

from app.db.database import engine
from app.services.slot_service import classify_city_slots


def main(city=None):
    with engine.connect() as conn:
        if city:
            cities = [city]
        else:
            cities = [
                row[0] for row in conn.execute(
                    text("SELECT DISTINCT city FROM locations ORDER BY city")
                ).fetchall()
            ]

    print(f"Classifying {', '.join(cities)}")
    with engine.connect() as conn:
        for name in cities:
            updated = classify_city_slots(conn, name)
            print(f"  {name}: {updated} place(s) assigned a slot")

    with engine.connect() as conn:
        for row in conn.execute(text("""
            SELECT city, time_slot, COUNT(*) AS n
            FROM locations GROUP BY 1, 2 ORDER BY 1, 2
        """)).fetchall():
            print(f"  {row.city:<12} {row.time_slot or '(none)':<10} {row.n}")


if __name__ == "__main__":
    city_arg = None
    if "--city" in sys.argv:
        city_arg = sys.argv[sys.argv.index("--city") + 1]
    main(city_arg)
