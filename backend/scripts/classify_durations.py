"""Classify per-place visit durations.

One-time (and idempotent) pass: places already classified by the model are
skipped, so re-running only fills gaps.

    python -m scripts.classify_durations
    python -m scripts.classify_durations --city Vizag
"""

import sys

from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.duration_service import classify_city_durations


def main(city=None):
    with SessionLocal() as db:
        if city:
            cities = [city]
        else:
            cities = [
                row[0] for row in db.execute(
                    text("SELECT DISTINCT city FROM locations ORDER BY city")
                ).fetchall()
            ]

        print(f"Classifying durations for: {', '.join(cities)}")
        for name in cities:
            updated = classify_city_durations(db, name)
            print(f"  {name}: {updated} place(s) updated")

        print("\nResulting spread:")
        for row in db.execute(text("""
            SELECT city, visit_duration, COUNT(*) AS n
            FROM locations GROUP BY 1, 2 ORDER BY 1, 2
        """)).fetchall():
            print(f"  {row.city:<12} {row.visit_duration:>4} min  {row.n} place(s)")


if __name__ == "__main__":
    city_arg = None
    if "--city" in sys.argv:
        city_arg = sys.argv[sys.argv.index("--city") + 1]
    main(city_arg)
