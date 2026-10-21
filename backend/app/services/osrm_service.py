import hashlib
import json

import requests
from sqlalchemy import text

# Public OSRM demo server: free, no key, no traffic data. Treat it as
# best-effort -- every call is cached and every failure degrades to a straight
# line rather than breaking the map.
OSRM_BASE = "https://router.project-osrm.org"
PROFILES = {
    "driving": "driving",
    "walking": "foot",
    "bicycling": "bike",
    "transit": "driving",  # OSRM has no transit profile
}
TIMEOUT_SECONDS = 12


def route_key(points, mode):
    """Cache key for one day's route. Stop order is part of the identity."""
    signature = "|".join(f"{round(p['lat'], 5)},{round(p['lng'], 5)}" for p in points)
    return hashlib.sha1(f"{mode}:{signature}".encode("utf-8")).hexdigest()


def _fetch_route(points, mode):
    coordinates = ";".join(f"{p['lng']},{p['lat']}" for p in points)
    profile = PROFILES.get(mode, "driving")
    url = f"{OSRM_BASE}/route/v1/{profile}/{coordinates}"

    response = requests.get(
        url,
        params={"overview": "full", "geometries": "geojson", "steps": "false"},
        timeout=TIMEOUT_SECONDS,
    )
    data = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        print(f"OSRM: no route ({data.get('code')}: {data.get('message', '')})")
        return None

    route = data["routes"][0]
    return {
        "distance_meters": int(route.get("distance", 0)),
        "duration_minutes": round(route.get("duration", 0) / 60),
        "coordinates": route["geometry"]["coordinates"],  # GeoJSON: [lng, lat]
    }


def get_day_route(points, mode, db):
    """Road geometry for an ordered list of stops.

    Returns ``{"coordinates": [[lng, lat], ...], "distance_meters": int,
    "duration_minutes": int, "source": "osrm" | "cache" | "unavailable"}``.
    """
    if len(points) < 2:
        return {"coordinates": [], "distance_meters": 0, "duration_minutes": 0, "source": "unavailable"}

    mode = (mode or "driving").lower()
    key = route_key(points, mode)

    cached = db.execute(
        text("SELECT geometry, distance_meters, duration_minutes FROM route_cache WHERE id = :id"),
        {"id": key},
    ).fetchone()

    if cached and cached.geometry:
        geometry = cached.geometry
        if isinstance(geometry, str):
            try:
                geometry = json.loads(geometry)
            except json.JSONDecodeError:
                geometry = []
        return {
            "coordinates": geometry or [],
            "distance_meters": cached.distance_meters or 0,
            "duration_minutes": cached.duration_minutes or 0,
            "source": "cache",
        }

    try:
        fetched = _fetch_route(points, mode)
    except Exception as exc:  # noqa: BLE001 - OSRM is decorative, never fatal
        print(f"OSRM: request failed ({type(exc).__name__}: {exc})")
        fetched = None

    if not fetched:
        return {"coordinates": [], "distance_meters": 0, "duration_minutes": 0, "source": "unavailable"}

    try:
        db.execute(
            text("""
                INSERT INTO route_cache
                    (id, travel_mode, distance_meters, duration_minutes, geometry, fetched_at)
                VALUES (:id, :mode, :distance, :duration, :geometry, NOW())
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": key,
                "mode": mode,
                "distance": fetched["distance_meters"],
                "duration": fetched["duration_minutes"],
                "geometry": json.dumps(fetched["coordinates"]),
            },
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        print(f"OSRM: cache write failed ({type(exc).__name__}: {exc}); continuing")
        db.rollback()

    return {
        "coordinates": fetched["coordinates"],
        "distance_meters": fetched["distance_meters"],
        "duration_minutes": fetched["duration_minutes"],
        "source": "osrm",
    }
