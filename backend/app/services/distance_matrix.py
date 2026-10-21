import math

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

# Google's Distance Matrix accepts at most 25 origins/destinations and 100
# elements per request. 10x10 stays inside both limits with headroom.
MAX_CHUNK = 10

SPEEDS_KMH = {
    "driving": 28.0,
    "walking": 4.8,
    "bicycling": 15.0,
    "transit": 20.0,
}
DEFAULT_SPEED_KMH = 25.0


def _cache_id(origin_id, destination_id, mode):
    return f"{origin_id}_{destination_id}_{mode}"


def _chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def haversine_meters(lat1, lng1, lat2, lng2):
    radius = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def estimate_minutes(loc_a, loc_b, mode):
    """Straight-line fallback, used only when Google cannot answer a leg.

    Never cached -- an estimate must not masquerade as a measured leg.
    """
    km = haversine_meters(loc_a["lat"], loc_a["lng"], loc_b["lat"], loc_b["lng"]) / 1000.0
    speed = SPEEDS_KMH.get(mode, DEFAULT_SPEED_KMH)
    return max(3, round(km / speed * 60))


def _fetch_chunk(origins, destinations, locations_data, mode):
    """One Distance Matrix call for a <=10x10 block. Returns {(i, j): minutes}."""
    origins_param = "|".join(
        f"{locations_data[i]['lat']},{locations_data[i]['lng']}" for i in origins
    )
    destinations_param = "|".join(
        f"{locations_data[j]['lat']},{locations_data[j]['lng']}" for j in destinations
    )

    response = requests.get(
        "https://maps.googleapis.com/maps/api/distancematrix/json",
        params={
            "origins": origins_param,
            "destinations": destinations_param,
            "mode": mode,
            "key": settings.PLACES_API_KEY,
        },
        timeout=15,
    )
    data = response.json()

    if data.get("status") != "OK":
        print(
            "DISTANCE: chunk rejected "
            f"({data.get('status')}: {data.get('error_message', '')}) -- estimating instead"
        )
        return {}

    resolved = {}
    for origin_pos, row in enumerate(data.get("rows", [])):
        for destination_pos, element in enumerate(row.get("elements", [])):
            if element.get("status") == "OK":
                resolved[(origins[origin_pos], destinations[destination_pos])] = (
                    element["duration"]["value"] // 60
                )
    return resolved


def get_or_fetch_distance_matrix(locations_data: list, mode: str, db: Session) -> list:
    """Full travel-time matrix for one day, cached per ordered place pair."""
    n = len(locations_data)
    matrix = [[0] * n for _ in range(n)]
    if n < 2:
        return matrix

    mode = (mode or "driving").lower()

    pair_cache_ids = {}
    for i in range(n):
        for j in range(n):
            if i != j:
                pair_cache_ids[(i, j)] = _cache_id(
                    locations_data[i]["place_id"], locations_data[j]["place_id"], mode
                )

    cached = {}
    ids = sorted(set(pair_cache_ids.values()))
    for chunk in _chunks(ids, 500):
        rows = db.execute(
            text("SELECT id, duration_minutes FROM distance_cache WHERE id = ANY(:ids)"),
            {"ids": chunk},
        ).fetchall()
        for row in rows:
            cached[row.id] = row.duration_minutes

    missing = []
    for (i, j), cache_id in pair_cache_ids.items():
        if cached.get(cache_id) is not None:
            matrix[i][j] = cached[cache_id]
        else:
            missing.append((i, j, cache_id))

    if not missing:
        return matrix

    needed = {(i, j) for i, j, _ in missing}
    origin_indices = sorted({i for i, _ in needed})
    destination_indices = sorted({j for _, j in needed})

    fetched = {}
    for origin_block in _chunks(origin_indices, MAX_CHUNK):
        for destination_block in _chunks(destination_indices, MAX_CHUNK):
            block_pairs = [
                (i, j)
                for i in origin_block
                for j in destination_block
                if (i, j) in needed and (i, j) not in fetched
            ]
            if not block_pairs:
                continue
            try:
                fetched.update(
                    _fetch_chunk(origin_block, destination_block, locations_data, mode)
                )
            except Exception as exc:  # noqa: BLE001 - degrade, never fabricate silently
                print(f"DISTANCE: chunk failed ({type(exc).__name__}: {exc}) -- estimating instead")

    # Persist only measured legs. Blocks return a full cross product, so the
    # diagonal (i == j) arrives too and has no cache key of its own.
    rows_to_write = []
    for (i, j), minutes in fetched.items():
        if i == j:
            continue
        matrix[i][j] = minutes
        rows_to_write.append({
            "id": pair_cache_ids[(i, j)],
            "origin": locations_data[i]["place_id"],
            "destination": locations_data[j]["place_id"],
            "mode": mode,
            "duration": minutes,
        })

    if rows_to_write:
        try:
            db.execute(
                text("""
                    INSERT INTO distance_cache
                        (id, origin_place_id, destination_place_id, travel_mode, duration_minutes, fetched_at)
                    VALUES (:id, :origin, :destination, :mode, :duration, NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                rows_to_write,
            )
            db.commit()
        except Exception as exc:  # noqa: BLE001
            print(f"DISTANCE: cache write failed ({type(exc).__name__}: {exc}); continuing")
            db.rollback()

    estimated = 0
    for i, j, _ in missing:
        if (i, j) not in fetched:
            matrix[i][j] = estimate_minutes(locations_data[i], locations_data[j], mode)
            estimated += 1

    print(
        f"DISTANCE: {len(missing)} uncached leg(s) for {n} stops -- "
        f"{len(fetched)} measured, {estimated} estimated"
    )
    return matrix
