"""Duplicate-place hygiene: detect, merge, and stop new ones entering.

Google returns one physical site under several names (Bhavani Island and
Bhavani Island Park sit 270 m apart), so identity is decided on normalized
names inside a short radius rather than on place id alone.
"""

from collections import defaultdict

from sqlalchemy import text

from app.services.dedupe_service import (
    NEAR_DUPLICATE_RADIUS_METERS,
    distance_meters,
    names_likely_same,
)

SELECT_PLACES = """
    SELECT place_id, name, city, rating, user_ratings_total,
           ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng
    FROM locations
    {where}
    ORDER BY city, rating DESC NULLS LAST, user_ratings_total DESC NULLS LAST
"""


def find_near_duplicate_pairs(db, city: str | None = None, radius_meters: int = NEAR_DUPLICATE_RADIUS_METERS):
    """Return ``[(loser_row, keeper_row, meters)]``.

    The keeper is the better-rated row because the query is ordered that way,
    so the first member of a cluster always wins.
    """
    where = "WHERE city = :city" if city else ""
    params = {"city": city} if city else {}
    rows = db.execute(text(SELECT_PLACES.format(where=where)), params).fetchall()

    buckets = defaultdict(list)
    for row in rows:
        buckets[row.city].append(row)

    pairs = []
    for places in buckets.values():
        kept = []
        for row in places:
            twin = None
            for existing in kept:
                gap = distance_meters(
                    float(row.lat), float(row.lng), float(existing.lat), float(existing.lng)
                )
                if gap <= radius_meters and names_likely_same(row.name, existing.name):
                    twin = (existing, gap)
                    break
            if twin:
                pairs.append((row, twin[0], twin[1]))
            else:
                kept.append(row)

    return pairs


def merge_pairs(db, pairs) -> int:
    """Fold each loser into its keeper. Safe to call inside one transaction."""
    merged = 0
    for loser, keeper, _gap in pairs:
        db.execute(
            text("UPDATE itinerary_stops SET place_id = :keeper WHERE place_id = :loser"),
            {"keeper": keeper.place_id, "loser": loser.place_id},
        )
        # Cached legs are keyed by place id, so the loser's legs cannot be reused.
        db.execute(
            text("""
                DELETE FROM distance_cache
                WHERE origin_place_id = :loser OR destination_place_id = :loser
            """),
            {"loser": loser.place_id},
        )
        db.execute(text("DELETE FROM locations WHERE place_id = :loser"), {"loser": loser.place_id})
        merged += 1

    if merged:
        # If two stops in one trip collapsed onto the same keeper, keep one.
        db.execute(text("""
            DELETE FROM itinerary_stops a
            USING itinerary_stops b
            WHERE a.trip_id = b.trip_id
              AND a.place_id = b.place_id
              AND a.ctid > b.ctid
        """))

    return merged


def dedupe_city(db, city: str) -> int:
    """Merge duplicates for one city; called right after a fresh ingest."""
    pairs = find_near_duplicate_pairs(db, city)
    if not pairs:
        return 0

    merged = merge_pairs(db, pairs)
    db.commit()
    for loser, keeper, gap in pairs:
        print(f"DEDUPE: merged '{loser.name}' into '{keeper.name}' ({round(gap)} m apart)")
    return merged
