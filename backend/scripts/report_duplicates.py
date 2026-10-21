"""Dry-run report: which stored places are near-duplicates of each other.

Read-only. Prints candidate pairs per city; deletes nothing.

    python -m scripts.report_duplicates
"""

from collections import defaultdict

from sqlalchemy import text

from app.db.database import engine
from app.services.dedupe_service import NEAR_DUPLICATE_RADIUS_METERS, distance_meters, names_likely_same


def main():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT place_id, name, city, rating,
                   ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng
            FROM locations
            ORDER BY city, rating DESC NULLS LAST
        """)).fetchall()

    by_city = defaultdict(list)
    for row in rows:
        by_city[row.city].append(row)

    total_pairs = 0
    for city, places in sorted(by_city.items()):
        kept, pairs = [], []
        for row in places:
            twin = None
            for existing in kept:
                gap = distance_meters(
                    float(row.lat), float(row.lng), float(existing.lat), float(existing.lng)
                )
                if gap <= NEAR_DUPLICATE_RADIUS_METERS and names_likely_same(row.name, existing.name):
                    twin = (existing, gap)
                    break
            if twin:
                pairs.append((row, twin[0], twin[1]))
            else:
                kept.append(row)

        total_pairs += len(pairs)
        print(f"\n{city}: {len(places)} places, {len(pairs)} near-duplicate pair(s), "
              f"{len(kept)} would remain")
        for row, existing, gap in pairs:
            print(f"  - drop '{row.name}' (rating {row.rating}) keep '{existing.name}' "
                  f"-- {round(gap)} m apart")

    print(f"\nTOTAL duplicate rows that would be merged away: {total_pairs}")


if __name__ == "__main__":
    main()
