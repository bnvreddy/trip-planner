import json
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.auth_service import get_current_user
from app.schemas.trip_schema import (
    AddStopRequest,
    DurationRequest,
    PreviewRequest,
    ReorderRequest,
    ReplaceRequest,
    TripRequest,
)
from app.services.dedupe_service import collapse_near_duplicates
from app.services.distance_matrix import estimate_minutes
from app.services.duration_service import classify_city_durations
from app.services.keyword_coverage import uncovered_keywords
from app.services.llm_service import curate_and_group_places_with_llm
from app.services.osrm_service import get_day_route
from app.services.place_hygiene import dedupe_city
from app.services.places_service import fetch_and_cache_places_from_google, parse_time_window
from app.services.planning_service import (
    cluster_by_location,
    plan_day as llm_plan_day,
    sequence_order,
)
from app.services.replacement_service import choose_replacement, find_replacement_candidates
from app.services.slot_service import classify_city_slots, rule_slot, slot_window

router = APIRouter()

DEFAULT_DAY_START_MIN = 540
DEFAULT_DAY_END_MIN = 1080
DEFAULT_VISIT_MINUTES = 90

# A day is considered "starved" below this and gets a second, slot-free pass.
MAX_STOPS_PER_DAY = 6
REFILL_RADIUS_METERS = 6000

QUALITY_EXPR = """((COALESCE(l.rating, 0) / 5.0) * 0.6
             + LEAST(LOG(COALESCE(l.user_ratings_total, 0) + 1) / 4.0, 1.0) * 0.4)"""

DAY_STOP_SELECT = """
    SELECT i.id AS stop_id, i.place_id, i.day_number, i.is_locked, i.guide_note,
           i.duration_minutes, i.scheduled_start, i.scheduled_end,
           l.name, l.visit_duration, l.operating_hours, l.time_slot, l.hours_source,
           l.primary_category, l.rating,
           ST_X(l.geom::geometry) AS lng, ST_Y(l.geom::geometry) AS lat,
           """ + QUALITY_EXPR + """ AS quality_score
    FROM itinerary_stops i
    JOIN locations l ON i.place_id = l.place_id
    WHERE i.trip_id = :trip_id AND i.day_number = :day_number
    ORDER BY i.scheduled_start ASC NULLS LAST
"""

ITINERARY_SELECT = """
    SELECT i.id AS stop_id, i.day_number, i.scheduled_start, i.scheduled_end, i.is_locked,
           i.status, i.guide_note,
           COALESCE(i.duration_minutes, l.visit_duration, 90) AS duration_minutes,
           l.name, l.city, l.photo_url, l.rating, l.primary_category, l.operating_hours,
           l.time_slot, ST_X(l.geom::geometry) AS lng, ST_Y(l.geom::geometry) AS lat
    FROM itinerary_stops i
    JOIN locations l ON i.place_id = l.place_id
    WHERE i.trip_id = :trip_id
    ORDER BY i.day_number ASC, i.scheduled_start ASC
"""

INSERT_STOP_SQL = """
    INSERT INTO itinerary_stops
        (id, trip_id, place_id, day_number, scheduled_start, scheduled_end,
         status, is_locked, duration_minutes)
    VALUES
        (:id, :trip_id, :place_id, :day_number, :start, :end,
         'PENDING', :is_locked, :duration)
"""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def ensure_valid_uuid(input_id: str) -> str:
    try:
        return str(uuid.UUID(input_id))
    except (ValueError, AttributeError, TypeError):
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(input_id)))


def minutes_from_time(value, default: int) -> int:
    if value is None:
        return default
    if hasattr(value, "hour"):
        return value.hour * 60 + value.minute
    try:
        hours, minutes = str(value).split(":")[:2]
        return int(hours) * 60 + int(minutes)
    except (TypeError, ValueError):
        return default


def parse_window(daily_start_time: str, daily_end_time: str):
    start = minutes_from_time(daily_start_time, DEFAULT_DAY_START_MIN)
    end = minutes_from_time(daily_end_time, DEFAULT_DAY_END_MIN)
    if end <= start:
        raise HTTPException(status_code=400, detail="Daily end time must be after the start time.")
    return start, end


def trip_window(trip, day_number: int = 1) -> tuple:
    """Window for one day: a per-day override wins, otherwise the trip default."""
    start = minutes_from_time(getattr(trip, "day_start_time", None), DEFAULT_DAY_START_MIN)
    end = minutes_from_time(getattr(trip, "day_end_time", None), DEFAULT_DAY_END_MIN)

    windows = getattr(trip, "day_windows", None)
    if isinstance(windows, str):
        try:
            windows = json.loads(windows)
        except json.JSONDecodeError:
            windows = None

    if isinstance(windows, list) and 0 < day_number <= len(windows):
        entry = windows[day_number - 1]
        if isinstance(entry, dict):
            day_start = minutes_from_time(entry.get("start"), start)
            day_end = minutes_from_time(entry.get("end"), end)
            if day_end > day_start:
                return day_start, day_end

    return start, max(end, start + 60)


def operating_bounds(row, day_start: int, day_end: int) -> tuple:
    """Opening hours, unless they are the ingest placeholder.

    Every stored place currently says 09:00-18:00 because the fetch throws the
    real hours away. Letting that placeholder close a beach at 18:00 is what
    produced "doesn't fit" on a half-empty day, so assumed hours constrain
    nothing beyond the traveller's own window.
    """
    if getattr(row, "hours_source", None) != "google":
        return day_start, day_end
    return parse_time_window(row.operating_hours)


def effective_duration(row, default: int = DEFAULT_VISIT_MINUTES) -> int:
    """Per-stop override wins; otherwise the place's own estimate."""
    override = getattr(row, "duration_minutes", None)
    if override:
        return int(override)
    base = getattr(row, "visit_duration", None)
    return int(base) if base else default


def _trip_row(db: Session, trip_id: str):
    trip = db.execute(
        text("""
            SELECT id, city, days_count, start_date, end_date, transport_mode,
                   day_start_time, day_end_time, day_windows
            FROM trips WHERE id = :tid
        """),
        {"tid": trip_id},
    ).fetchone()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


def touch_trip(db: Session, trip_id: str) -> None:
    db.execute(text("UPDATE trips SET updated_at = NOW() WHERE id = :tid"), {"tid": trip_id})


def row_slot(row) -> str:
    return getattr(row, "time_slot", None) or rule_slot(
        getattr(row, "primary_category", None), getattr(row, "name", "")
    )


def build_day_inputs(rows, day_start: int, day_end: int, use_slots: bool = True, pinned_ids=frozenset()):
    """Turn DB rows into optimizer input.

    Effective window = opening hours ∩ traveller's day ∩ the place's time slot.
    A stop that cannot fit that intersection is reported, never scheduled past
    its closing time (the old behaviour allowed a day to end at 19:47).
    """
    locations, durations, dropped = [], [], []

    for row in rows:
        duration = effective_duration(row)
        open_min, close_min = operating_bounds(row, day_start, day_end)
        slot = row_slot(row)

        window_start = max(open_min, day_start)
        window_end = min(close_min, day_end)

        if use_slots:
            limits = slot_window(slot, day_start, day_end)
            if limits is None:
                dropped.append({
                    "place_name": row.name,
                    "reason": f"its {slot} slot falls outside the daily window",
                    "needed_minutes": duration,
                    "free_minutes": 0,
                    "slot": slot,
                })
                continue
            window_start = max(window_start, limits[0])
            window_end = min(window_end, limits[1])

        free = max(0, window_end - window_start)
        if free < duration:
            dropped.append({
                "place_name": row.name,
                "reason": (
                    f"needs {duration} min but only {free} min of its {slot} slot is free"
                    if use_slots
                    else f"needs {duration} min but only {free} min of the day is free"
                ),
                "needed_minutes": duration,
                "free_minutes": free,
                "slot": slot,
            })
            continue

        locations.append({
            "place_id": row.place_id,
            "name": row.name,
            "time_window": (window_start, window_end),
            "lat": float(row.lat),
            "lng": float(row.lng),
            "quality_score": float(row.quality_score or 0.8),
            "is_locked": bool(row.is_locked) or row.place_id in pinned_ids,
            "slot": slot,
        })
        durations.append(duration)

    return locations, durations, dropped


def _save_day(trip_id, day_number, day_date, route, overrides, locks, db,
              existing_ids_by_place=None):
    """Rewrite one day's stops, keeping the row id of a place that stays put.

    Stable ids matter: the UI, in-flight requests and lock state all address a
    stop by id, so a re-plan must not invent new ones for unchanged places.
    """
    existing_ids_by_place = existing_ids_by_place or {}
    db.execute(
        text("DELETE FROM itinerary_stops WHERE trip_id = :tid AND day_number = :day"),
        {"tid": trip_id, "day": day_number},
    )
    midnight = datetime.combine(day_date, datetime.min.time())

    for stop in route:
        place_id = stop["place_id"]
        db.execute(
            text(INSERT_STOP_SQL),
            {
                "id": existing_ids_by_place.get(place_id) or str(uuid.uuid4()),
                "trip_id": trip_id,
                "place_id": place_id,
                "day_number": day_number,
                "start": midnight + timedelta(minutes=stop["arrival_minute"]),
                "end": midnight + timedelta(minutes=stop["departure_minute"]),
                "is_locked": locks.get(place_id, False),
                "duration": overrides.get(place_id),
            },
        )


def plan_rows(rows, trip, day_number: int, db: Session, use_slots: bool = True,
              pinned_ids=frozenset()) -> dict:
    """Plan one day: the LLM proposes, the calculator verifies, never silently broken."""
    day_start, day_end = trip_window(trip, day_number)
    locations, durations, dropped = build_day_inputs(rows, day_start, day_end, use_slots, pinned_ids)

    result = {
        "scheduled": [],
        "dropped": dropped,
        "considered": len(rows),
        "day_start": day_start,
        "day_end": day_end,
        "source": "empty",
        "problems": [],
    }
    if not locations:
        return result

    duration_by_place = {
        loc["place_id"]: durations[index] for index, loc in enumerate(locations)
    }

    planned = llm_plan_day(
        locations,
        duration_by_place,
        day_start,
        day_end,
        city=trip.city,
        mode=(trip.transport_mode or "driving").lower(),
    )

    result["scheduled"] = planned["scheduled"]
    result["dropped"] = result["dropped"] + planned["unplaced"]
    result["source"] = planned["source"]
    result["problems"] = planned.get("problems", [])

    scheduled_ids = {stop["place_id"] for stop in planned["scheduled"]}
    already_reported = {
        (item.get("place_name"), item.get("slot")) for item in result["dropped"]
    }
    for loc in locations:
        if loc["place_id"] in scheduled_ids:
            continue
        if (loc["name"], loc.get("slot")) in already_reported:
            continue
        result["dropped"].append({
            "place_name": loc["name"],
            "reason": "the day had no room left for it",
            "needed_minutes": duration_by_place.get(loc["place_id"]),
            "free_minutes": 0,
            "slot": loc.get("slot"),
        })

    return result


def simulate_day(rows, trip, day_number: int, db: Session, pinned_ids=frozenset()) -> dict:
    """What the planner would produce for these rows -- identical to the real path."""
    planned = plan_rows(rows, trip, day_number, db, use_slots=True, pinned_ids=pinned_ids)
    planned["relaxed"] = False
    return planned


def optimize_day(trip_id: str, day_number: int, trip, db: Session, use_slots: bool = True,
                 pinned_ids=frozenset()) -> dict:
    """Plan one day from the stops it currently holds and persist the result."""
    rows = db.execute(
        text(DAY_STOP_SELECT), {"trip_id": trip_id, "day_number": day_number}
    ).fetchall()
    if not rows:
        return {"dropped": [], "scheduled": [], "considered": 0}

    planned = plan_rows(rows, trip, day_number, db, use_slots, pinned_ids)

    overrides = {row.place_id: row.duration_minutes for row in rows if row.duration_minutes}
    locks = {row.place_id: bool(row.is_locked) for row in rows}
    day_date = trip.start_date + timedelta(days=day_number - 1)

    if not planned["scheduled"]:
        db.execute(
            text("DELETE FROM itinerary_stops WHERE trip_id = :tid AND day_number = :day"),
            {"tid": trip_id, "day": day_number},
        )
        db.commit()
        return planned

    existing_ids = {row.place_id: row.stop_id for row in rows}
    _save_day(trip_id, day_number, day_date, planned["scheduled"],
              overrides, locks, db, existing_ids)
    db.commit()

    return planned


def suggest_for_day(trip_id: str, day_number: int, trip, db: Session, limit: int = 3) -> list:
    """Places that would fit this day -- offered, never inserted.

    Off-theme additions used to happen silently; now the traveller is asked.
    """
    rows = db.execute(
        text(DAY_STOP_SELECT), {"trip_id": trip_id, "day_number": day_number}
    ).fetchall()
    if len(rows) >= MAX_STOPS_PER_DAY:
        return []

    day_start, day_end = trip_window(trip, day_number)
    mode = (trip.transport_mode or "driving").lower()

    taken = [row[0] for row in db.execute(
        text("SELECT place_id FROM itinerary_stops WHERE trip_id = :tid"), {"tid": trip_id}
    ).fetchall()]

    if rows:
        centre = {
            "lat": sum(float(row.lat) for row in rows) / len(rows),
            "lng": sum(float(row.lng) for row in rows) / len(rows),
        }
        radius_clause = ("AND ST_DWithin(geom::geography, "
                         "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)")
        params = {"city": trip.city, "lng": centre["lng"], "lat": centre["lat"],
                  "radius": REFILL_RADIUS_METERS}
    else:
        radius_clause = ""
        params = {"city": trip.city}

    params["taken"] = sorted(set(taken)) or [""]

    candidates = db.execute(text(f"""
        SELECT place_id, name, primary_category, category_tags, rating, visit_duration,
               operating_hours, time_slot,
               ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng
        FROM locations
        WHERE city = :city
          AND place_id <> ALL(:taken)
          AND COALESCE(rating, 0) >= 4.0
          {radius_clause}
        ORDER BY """ + QUALITY_EXPR.replace("l.", "") + """ DESC
        LIMIT 20
    """), params).fetchall()

    scheduled = [
        {
            "place_id": row.place_id,
            "name": row.name,
            "slot": row_slot(row),
            "time_window": (
                max(day_start, slot_window(row_slot(row), day_start, day_end)[0]),
                min(day_end, slot_window(row_slot(row), day_start, day_end)[1]),
            ),
        }
        for row in rows
    ]
    durations = {row.place_id: effective_duration(row) for row in rows}
    _schedule, _unplaced = sequence_order(
        scheduled, durations, day_start, day_end, mode, allow_overrun=True
    )
    last_end = max(
        (stop["departure_minute"] for stop in _schedule), default=day_start
    )

    suggestions = []
    for row in candidates:
        slot = row_slot(row)
        limits = slot_window(slot, day_start, day_end)
        if limits is None:
            continue

        duration = row.visit_duration or DEFAULT_VISIT_MINUTES
        travel = estimate_minutes(
            {"lat": float(row.lat), "lng": float(row.lng)},
            {"lat": float(rows[-1].lat), "lng": float(rows[-1].lng)},
            mode,
        ) if rows else 0

        arrival = max(last_end + travel, limits[0])
        if arrival + duration > min(limits[1], day_end):
            continue

        suggestions.append({
            "place_id": row.place_id,
            "place_name": row.name,
            "slot": slot,
            "duration_minutes": duration,
            "at": f"{arrival // 60:02d}:{arrival % 60:02d}",
            "reason": f"fits the {slot} window on Day {day_number}",
        })
        if len(suggestions) >= limit:
            break

    return suggestions


def plan_day(trip_id: str, day_number: int, trip, db: Session, allow_refill: bool = False,
             max_new: int = 0, pinned_ids=frozenset(),
             exclude_from_refill=frozenset()) -> dict:
    """Plan one day and report what changed. Nothing is added without asking."""
    before_rows = db.execute(
        text(DAY_STOP_SELECT), {"trip_id": trip_id, "day_number": day_number}
    ).fetchall()
    if not before_rows:
        return {"dropped": [], "scheduled": [], "added": [], "relaxed": False}

    before_ids = {row.place_id for row in before_rows}
    result = optimize_day(trip_id, day_number, trip, db, use_slots=True, pinned_ids=pinned_ids)

    final_ids = {stop["place_id"] for stop in result["scheduled"]}
    added_ids = final_ids - before_ids
    added = []
    if added_ids:
        added_rows = db.execute(
            text("SELECT place_id, name FROM locations WHERE place_id = ANY(:ids)"),
            {"ids": list(added_ids)},
        ).fetchall()
        added = [{"place_name": row.name} for row in added_rows]

    result["added"] = added
    result["relaxed"] = False
    return result


def itinerary_payload(trip_id: str, db: Session, raise_if_empty: bool = True) -> dict:
    stops = db.execute(text(ITINERARY_SELECT), {"trip_id": trip_id}).fetchall()
    trip = db.execute(
        text("""
            SELECT city, days_count, transport_mode, day_start_time, day_end_time
            FROM trips WHERE id = :tid
        """),
        {"tid": trip_id},
    ).fetchone()

    if not stops and raise_if_empty:
        raise HTTPException(status_code=404, detail="Trip itinerary not found")

    return {
        "trip_id": trip_id,
        "destination": trip.city if trip else "Unknown",
        "days_count": trip.days_count if trip else 1,
        "transport_mode": trip.transport_mode if trip else "driving",
        "daily_start_time": trip.day_start_time.strftime("%H:%M") if trip and trip.day_start_time else "09:00",
        "daily_end_time": trip.day_end_time.strftime("%H:%M") if trip and trip.day_end_time else "18:00",
        "stops": [{
            "stop_id": stop.stop_id,
            "day_number": stop.day_number,
            "place_name": stop.name,
            "city": stop.city,
            "photo_url": stop.photo_url,
            "rating": stop.rating,
            "primary_category": stop.primary_category,
            "operating_hours": stop.operating_hours,
            "time_slot": stop.time_slot,
            "duration_minutes": stop.duration_minutes,
            "scheduled_start": str(stop.scheduled_start),
            "scheduled_end": str(stop.scheduled_end),
            "status": stop.status,
            "is_locked": stop.is_locked,
            "guide_note": stop.guide_note,
            "lat": stop.lat,
            "lng": stop.lng,
        } for stop in stops],
    }


# --------------------------------------------------------------------------- #
# trip creation
# --------------------------------------------------------------------------- #

@router.post("/trips/generate")
def generate_trip(payload: TripRequest, db: Session = Depends(get_db)):
    city = (payload.destination_city or "").strip()
    if not city:
        raise HTTPException(status_code=400, detail="destination_city is required.")

    safe_user_id = ensure_valid_uuid(payload.user_id)
    parse_window(payload.daily_start_time, payload.daily_end_time)

    try:
        start_dt = datetime.strptime(payload.start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(payload.end_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Dates must be formatted YYYY-MM-DD.")

    if end_dt < start_dt:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date.")

    days_count = max(1, (end_dt - start_dt).days + 1)

    # Catalogue policy: reuse what is stored. Google is consulted only when the
    # city is empty, or when a selected keyword has no matching place at all --
    # in that case only the uncovered keywords are fetched.
    stored_places = db.execute(
        text("SELECT COUNT(*) FROM locations WHERE city = :city"), {"city": city}
    ).scalar()

    fetched_for = []
    if stored_places == 0:
        fetch_and_cache_places_from_google(city, payload.selected_keywords, db)
        dedupe_city(db, city)
        fetched_for = list(payload.selected_keywords)
    elif payload.selected_keywords:
        missing = uncovered_keywords(db, city, payload.selected_keywords)
        if missing:
            fetch_and_cache_places_from_google(city, missing, db)
            dedupe_city(db, city)
            fetched_for = missing

    classify_city_slots(db, city)
    classify_city_durations(db, city)

    candidate_limit = max(20, days_count * 15)
    db_locations = db.execute(text("""
        SELECT place_id, name, operating_hours, visit_duration, rating, photo_url,
               primary_category, category_tags, time_slot,
               ST_X(geom::geometry) as lng, ST_Y(geom::geometry) as lat,
               """ + QUALITY_EXPR + """ AS quality_score
        FROM locations l
        WHERE city = :city AND (rating >= 3.8 OR rating = 0.0)
        ORDER BY quality_score DESC
        LIMIT :limit
    """), {"city": city, "limit": candidate_limit}).fetchall()

    if not db_locations:
        raise HTTPException(status_code=404, detail="No suitable locations found.")

    db_locations, duplicates = collapse_near_duplicates(db_locations)

    candidates_for_llm = [{
        "place_id": loc.place_id,
        "name": loc.name,
        "types": loc.category_tags,
        "rating": loc.rating,
        "primary_category": loc.primary_category,
        "slot": loc.time_slot,
    } for loc in db_locations]

    # The LLM curates *which* places are worth visiting; geography decides which
    # day each one lands on. Letting the model (or a slot-capacity shuffle) pick
    # the days is what scattered a single day across the whole city.
    raw_grouping = curate_and_group_places_with_llm(
        payload.selected_keywords, candidates_for_llm, days_count
    )

    valid_by_id = {loc.place_id: loc for loc in db_locations}
    selected_ids = []
    seen_selected = set()
    if isinstance(raw_grouping, dict):
        for bucket in raw_grouping.values():
            if not isinstance(bucket, list):
                continue
            for place_id in bucket:
                place_id = str(place_id)
                if place_id in valid_by_id and place_id not in seen_selected:
                    seen_selected.add(place_id)
                    selected_ids.append(place_id)

    # No usable curation (model offline, or nothing matched): fall back to the
    # quality-ranked catalogue order already loaded above.
    if not selected_ids:
        selected_ids = [loc.place_id for loc in db_locations]

    # Keep the plan to roughly six stops a day before clustering; the per-day
    # scheduler trims anything that still cannot fit the clock.
    selected_ids = selected_ids[: days_count * 6]

    places_for_cluster = [
        {
            "place_id": place_id,
            "lat": float(valid_by_id[place_id].lat),
            "lng": float(valid_by_id[place_id].lng),
        }
        for place_id in selected_ids
    ]
    grouped = cluster_by_location(places_for_cluster, days_count)
    unbalanced = []

    if not db.execute(text("SELECT user_id FROM users WHERE user_id = :uid"), {"uid": safe_user_id}).fetchone():
        db.execute(
            text("INSERT INTO users (user_id, email, default_transport_mode) VALUES (:uid, :email, 'Driving')"),
            {"uid": safe_user_id, "email": f"demo-{safe_user_id}@example.com"},
        )
        db.commit()

    new_trip_id = str(uuid.uuid4())

    day_windows = []
    for entry in payload.daily_windows[:days_count]:
        start_min = minutes_from_time(entry.start, DEFAULT_DAY_START_MIN)
        end_min = minutes_from_time(entry.end, DEFAULT_DAY_END_MIN)
        if end_min <= start_min:
            raise HTTPException(
                status_code=400,
                detail=f"Day window {entry.start}-{entry.end} ends before it starts.",
            )
        day_windows.append({"start": entry.start, "end": entry.end})

    db.execute(text("""
        INSERT INTO trips
            (id, user_id, city, days_count, created_at, start_date, end_date,
             transport_mode, day_start_time, day_end_time, day_windows, updated_at)
        VALUES
            (:trip_id, :user_id, :city, :days_count, NOW(), :start_date, :end_date,
             :transport_mode, CAST(:day_start AS TIME), CAST(:day_end AS TIME),
             CAST(:day_windows AS JSONB), NOW())
    """), {
        "trip_id": new_trip_id,
        "user_id": safe_user_id,
        "city": city,
        "days_count": days_count,
        "start_date": start_dt,
        "end_date": end_dt,
        "transport_mode": payload.transport_mode.lower(),
        "day_start": payload.daily_start_time,
        "day_end": payload.daily_end_time,
        "day_windows": json.dumps(day_windows) if day_windows else None,
    })

    for day in range(1, days_count + 1):
        for place_id in grouped[f"day_{day}"]:
            db.execute(text("""
                INSERT INTO itinerary_stops
                    (id, trip_id, place_id, day_number, status, is_locked)
                VALUES (:id, :trip_id, :place_id, :day, 'PENDING', FALSE)
            """), {
                "id": str(uuid.uuid4()),
                "trip_id": new_trip_id,
                "place_id": place_id,
                "day": day,
            })
    db.commit()

    trip = _trip_row(db, new_trip_id)
    dropped, added = list(unbalanced), []
    relaxed = False
    for day in range(1, days_count + 1):
        result = plan_day(new_trip_id, day, trip, db)
        dropped += result["dropped"]
        added += result["added"]

    touch_trip(db, new_trip_id)
    db.commit()

    return {
        "message": f"Successfully generated {days_count}-day itinerary!",
        "trip_id": new_trip_id,
        "days_count": days_count,
        "itinerary": itinerary_payload(new_trip_id, db, raise_if_empty=False),
        "dropped": dropped,
        "added": added,
        "relaxed": relaxed,
        "catalogue_fetched_for": fetched_for,
        "duplicates_merged": duplicates,
    }


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #

@router.get("/trips")
def list_trips(user_id: str | None = None, db: Session = Depends(get_db)):
    where_clause = ""
    params = {}
    if user_id:
        where_clause = "WHERE t.user_id = :user_id"
        params["user_id"] = ensure_valid_uuid(user_id)

    rows = db.execute(text(f"""
        SELECT t.id, t.city, t.days_count, t.start_date, t.end_date, t.transport_mode,
               t.created_at, COALESCE(t.updated_at, t.created_at) AS updated_at,
               COUNT(s.id) AS stop_count
        FROM trips t
        LEFT JOIN itinerary_stops s ON s.trip_id = t.id
        {where_clause}
        GROUP BY t.id, t.city, t.days_count, t.start_date, t.end_date,
                 t.transport_mode, t.created_at, t.updated_at
        ORDER BY COALESCE(t.updated_at, t.created_at) DESC
    """), params).fetchall()

    return {
        "trips": [{
            "trip_id": row.id,
            "city": row.city,
            "days_count": row.days_count,
            "start_date": str(row.start_date) if row.start_date else None,
            "end_date": str(row.end_date) if row.end_date else None,
            "transport_mode": row.transport_mode,
            "stop_count": row.stop_count,
            "updated_at": str(row.updated_at) if row.updated_at else None,
        } for row in rows]
    }


@router.get("/trips/{trip_id}/itinerary")
def get_trip_itinerary(trip_id: str, db: Session = Depends(get_db)):
    return itinerary_payload(trip_id, db)


@router.delete("/trips/{trip_id}")
def delete_trip(trip_id: str, current_user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Remove a trip and all of its stops. Only the owner may delete it."""
    trip = db.execute(
        text("SELECT id, user_id FROM trips WHERE id = :tid"), {"tid": trip_id}
    ).fetchone()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if str(trip.user_id) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="You can only delete your own trips.")

    db.execute(text("DELETE FROM itinerary_stops WHERE trip_id = :tid"), {"tid": trip_id})
    db.execute(text("DELETE FROM trips WHERE id = :tid"), {"tid": trip_id})
    db.commit()

    return {"message": "Trip deleted.", "trip_id": trip_id}


@router.get("/trips/{trip_id}/days/{day_number}/route")
def get_day_route_geometry(trip_id: str, day_number: int, db: Session = Depends(get_db)):
    trip = _trip_row(db, trip_id)

    points = db.execute(text("""
        SELECT l.name, ST_Y(l.geom::geometry) AS lat, ST_X(l.geom::geometry) AS lng
        FROM itinerary_stops i
        JOIN locations l ON i.place_id = l.place_id
        WHERE i.trip_id = :tid AND i.day_number = :day
        ORDER BY i.scheduled_start ASC
    """), {"tid": trip_id, "day": day_number}).fetchall()

    stops = [{"name": row.name, "lat": float(row.lat), "lng": float(row.lng)} for row in points]
    route = get_day_route(stops, (trip.transport_mode or "driving").lower(), db)

    return {
        "trip_id": trip_id,
        "day_number": day_number,
        "source": route["source"],
        # Leaflet wants [lat, lng]; GeoJSON is [lng, lat].
        "coordinates": [[lat, lng] for lng, lat in route["coordinates"]],
        "stop_coordinates": [[stop["lat"], stop["lng"]] for stop in stops],
        "distance_meters": route["distance_meters"],
        "duration_minutes": route["duration_minutes"],
    }


# --------------------------------------------------------------------------- #
# suggestions (offered, never inserted)
# --------------------------------------------------------------------------- #

@router.get("/trips/{trip_id}/days/{day_number}/suggestions")
def day_suggestions(trip_id: str, day_number: int, db: Session = Depends(get_db)):
    trip = _trip_row(db, trip_id)
    if not 1 <= day_number <= trip.days_count:
        raise HTTPException(status_code=400, detail=f"day_number must be between 1 and {trip.days_count}.")
    return {"day_number": day_number, "suggestions": suggest_for_day(trip_id, day_number, trip, db)}


@router.post("/trips/{trip_id}/days/{day_number}/add")
def add_stop_to_day(trip_id: str, day_number: int, payload: AddStopRequest,
                    db: Session = Depends(get_db)):
    """Accept one of the day's suggestions."""
    trip = _trip_row(db, trip_id)
    if not 1 <= day_number <= trip.days_count:
        raise HTTPException(status_code=400, detail=f"day_number must be between 1 and {trip.days_count}.")

    already = db.execute(text(
        "SELECT 1 FROM itinerary_stops WHERE trip_id = :tid AND place_id = :pid"
    ), {"tid": trip_id, "pid": payload.place_id}).fetchone()
    if already:
        raise HTTPException(status_code=400, detail="That place is already on this trip.")

    place = db.execute(
        text("SELECT name FROM locations WHERE place_id = :pid"), {"pid": payload.place_id}
    ).fetchone()
    if not place:
        raise HTTPException(status_code=404, detail="Place not found.")

    db.execute(text("""
        INSERT INTO itinerary_stops
            (id, trip_id, place_id, day_number, status, is_locked)
        VALUES (:id, :tid, :pid, :day, 'PENDING', FALSE)
    """), {
        "id": str(uuid.uuid4()),
        "tid": trip_id,
        "pid": payload.place_id,
        "day": day_number,
    })
    db.commit()

    result = plan_day(trip_id, day_number, trip, db)
    touch_trip(db, trip_id)
    db.commit()

    return {
        "message": f"Added {place.name} to Day {day_number}.",
        "itinerary": itinerary_payload(trip_id, db),
        "dropped": result["dropped"],
        "added": result["added"],
    }


# --------------------------------------------------------------------------- #
# editing
# --------------------------------------------------------------------------- #

@router.post("/trips/{trip_id}/stops/{stop_id}/lock")
def toggle_stop_lock(trip_id: str, stop_id: str, db: Session = Depends(get_db)):
    stop = db.execute(
        text("SELECT is_locked FROM itinerary_stops WHERE id = :sid AND trip_id = :tid"),
        {"sid": stop_id, "tid": trip_id},
    ).fetchone()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    new_lock_state = not stop.is_locked
    db.execute(
        text("UPDATE itinerary_stops SET is_locked = :locked WHERE id = :sid"),
        {"locked": new_lock_state, "sid": stop_id},
    )
    touch_trip(db, trip_id)
    db.commit()
    return {"message": f"Stop lock status updated to {new_lock_state}", "is_locked": new_lock_state}


@router.patch("/trips/{trip_id}/stops/reorder")
def reorder_stops(trip_id: str, payload: ReorderRequest, db: Session = Depends(get_db)):
    if not payload.ordered_stop_ids:
        raise HTTPException(status_code=400, detail="ordered_stop_ids cannot be empty.")

    trip = _trip_row(db, trip_id)
    rows = db.execute(
        text(DAY_STOP_SELECT), {"trip_id": trip_id, "day_number": payload.day_number}
    ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="No stops on that day")

    by_stop_id = {row.stop_id: row for row in rows}
    ordered = [by_stop_id[sid] for sid in payload.ordered_stop_ids if sid in by_stop_id]
    if len(ordered) != len(rows):
        raise HTTPException(
            status_code=400,
            detail="The new order must contain every stop of that day exactly once.",
        )

    day_start, day_end = trip_window(trip, payload.day_number)
    # A deliberate drag wins over the band preference and over the window: keep
    # every stop in the order the user asked for and report the conflicts.
    locations, durations, dropped = build_day_inputs(ordered, day_start, day_end, use_slots=False)
    mode = (trip.transport_mode or "driving").lower()

    duration_by_place = {loc["place_id"]: durations[i] for i, loc in enumerate(locations)}
    order_ids = [loc["place_id"] for loc in locations]
    route, unplaced = sequence_order(
        locations, duration_by_place, day_start, day_end,
        order_ids=order_ids, mode=mode, allow_overrun=True,
    )
    dropped += unplaced

    last_departure = max((stop["departure_minute"] for stop in route), default=day_start)
    overrun_minutes = max(0, last_departure - day_end)

    overrides = {row.place_id: row.duration_minutes for row in rows if row.duration_minutes}
    locks = {row.place_id: bool(row.is_locked) for row in rows}
    slot_by_place = {row.place_id: row_slot(row) for row in rows}

    outside_slot = []
    for stop in route:
        limits = slot_window(slot_by_place.get(stop["place_id"], "flexible"), day_start, day_end)
        if limits and not (limits[0] <= stop["arrival_minute"] <= limits[1]):
            outside_slot.append(stop["name"])

    day_date = trip.start_date + timedelta(days=payload.day_number - 1)
    existing_ids = {row.place_id: row.stop_id for row in rows}
    _save_day(trip_id, payload.day_number, day_date, route, overrides, locks, db, existing_ids)
    touch_trip(db, trip_id)
    db.commit()

    return {
        "message": "Stops reordered and times updated.",
        "itinerary": itinerary_payload(trip_id, db),
        "dropped": dropped,
        "outside_slot": outside_slot,
        "overrun_minutes": overrun_minutes,
    }


@router.patch("/trips/{trip_id}/stops/{stop_id}/duration")
def update_stop_duration(
    trip_id: str,
    stop_id: str,
    payload: DurationRequest,
    db: Session = Depends(get_db),
):
    """'I want to stay 30/60 minutes longer' -- re-optimizes the whole day."""
    trip = _trip_row(db, trip_id)
    stop = db.execute(
        text("SELECT id, day_number, place_id FROM itinerary_stops WHERE id = :sid AND trip_id = :tid"),
        {"sid": stop_id, "tid": trip_id},
    ).fetchone()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    db.execute(
        text("UPDATE itinerary_stops SET duration_minutes = :duration WHERE id = :sid"),
        {"duration": payload.duration_minutes, "sid": stop_id},
    )
    db.commit()

    result = plan_day(trip_id, stop.day_number, trip, db, pinned_ids={stop.place_id})
    touch_trip(db, trip_id)
    db.commit()

    return {
        "message": f"Day {stop.day_number} re-planned for a {payload.duration_minutes}-minute visit.",
        "day_number": stop.day_number,
        "duration_minutes": payload.duration_minutes,
        "itinerary": itinerary_payload(trip_id, db),
        "dropped": result["dropped"],
        "added": result["added"],
        "relaxed": result["relaxed"],
    }


@router.post("/trips/{trip_id}/stops/{stop_id}/move")
def move_stop(trip_id: str, stop_id: str, target_day: int, db: Session = Depends(get_db)):
    trip = _trip_row(db, trip_id)
    if not 1 <= target_day <= trip.days_count:
        raise HTTPException(status_code=400, detail=f"target_day must be between 1 and {trip.days_count}.")

    stop = db.execute(
        text("SELECT day_number, place_id FROM itinerary_stops WHERE id = :sid AND trip_id = :tid"),
        {"sid": stop_id, "tid": trip_id},
    ).fetchone()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    old_day = stop.day_number
    if old_day == target_day:
        return {
            "message": "Stop is already on that day.",
            "itinerary": itinerary_payload(trip_id, db),
            "dropped": [],
            "added": [],
        }

    db.execute(
        text("UPDATE itinerary_stops SET day_number = :day WHERE id = :sid"),
        {"day": target_day, "sid": stop_id},
    )
    db.commit()

    old_result = plan_day(trip_id, old_day, trip, db)
    # The moved stop must survive on its new day, even if something else has to give.
    new_result = plan_day(trip_id, target_day, trip, db, pinned_ids={stop.place_id})
    touch_trip(db, trip_id)
    db.commit()

    return {
        "message": f"Stop moved to Day {target_day} and both days re-planned.",
        "itinerary": itinerary_payload(trip_id, db),
        "dropped": old_result["dropped"] + new_result["dropped"],
        "added": old_result["added"] + new_result["added"],
        "relaxed": old_result["relaxed"] or new_result["relaxed"],
    }


def _trip_place_names(db: Session, trip_id: str, exclude_place_id: str | None = None):
    rows = db.execute(text("""
        SELECT l.place_id, l.name
        FROM itinerary_stops i JOIN locations l ON i.place_id = l.place_id
        WHERE i.trip_id = :tid
    """), {"tid": trip_id}).fetchall()
    return (
        {row.place_id for row in rows},
        [row.name for row in rows if row.place_id != exclude_place_id],
    )


def _hhmm(minutes):
    if minutes is None:
        return None
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _location_as_day_row(db: Session, place_id: str, day_number: int):
    """Shape a bare location like a DAY_STOP_SELECT row, for hypothetical days."""
    return db.execute(text("""
        SELECT NULL::text AS stop_id, :day AS day_number, FALSE AS is_locked,
               NULL::text AS guide_note, NULL::int AS duration_minutes,
               NULL::timestamp AS scheduled_start, NULL::timestamp AS scheduled_end,
               place_id, name, visit_duration, operating_hours, time_slot, hours_source,
               primary_category, rating,
               ST_X(geom::geometry) AS lng, ST_Y(geom::geometry) AS lat,
               """ + QUALITY_EXPR.replace("l.", "") + """ AS quality_score
        FROM locations WHERE place_id = :pid
    """), {"day": day_number, "pid": place_id}).fetchone()


def _as_variant(row, **overrides):
    data = dict(row._mapping)
    data.update(overrides)
    return SimpleNamespace(**data)


def _describe_changes(old_rows, new_schedule):
    """Human-readable diff between a stored day and a hypothetical one."""
    changes = []
    old_by_place = {row.place_id: row for row in old_rows}
    new_ids = set()

    for stop in new_schedule:
        new_ids.add(stop["place_id"])
        old = old_by_place.get(stop["place_id"])
        if old is None:
            changes.append({
                "place_name": stop["name"],
                "action": "add",
                "to": _hhmm(stop["arrival_minute"]),
            })
            continue

        old_start = minutes_from_time(getattr(old, "scheduled_start", None), None)
        if old_start is not None and old_start != stop["arrival_minute"]:
            changes.append({
                "place_name": stop["name"],
                "action": "move",
                "from": _hhmm(old_start),
                "to": _hhmm(stop["arrival_minute"]),
            })

    for place_id, row in old_by_place.items():
        if place_id not in new_ids:
            changes.append({"place_name": row.name, "action": "remove"})

    return changes


def _day_preview(day_number, old_rows, planned):
    old_ids = {row.place_id for row in old_rows}
    last_end = max((stop["departure_minute"] for stop in planned["scheduled"]), default=None)
    overrun = max(0, last_end - planned["day_end"]) if last_end is not None else 0

    return {
        "day_number": day_number,
        "start_time": _hhmm(planned["day_start"]),
        "end_time": _hhmm(planned["day_end"]),
        "changes": _describe_changes(old_rows, planned["scheduled"]),
        "added": [
            {"place_name": stop["name"], "at": _hhmm(stop["arrival_minute"])}
            for stop in planned["scheduled"] if stop["place_id"] not in old_ids
        ],
        "dropped": planned["dropped"],
        "relaxed": planned.get("relaxed", False),
        "resulting_stops": len(planned["scheduled"]),
        "last_end": _hhmm(last_end),
        "overrun_minutes": overrun,
    }


@router.post("/trips/{trip_id}/stops/{stop_id}/preview")
def preview_stop_change(trip_id: str, stop_id: str, payload: PreviewRequest, db: Session = Depends(get_db)):
    """Report exactly what an edit would change, and change nothing.

    Runs the same pure planner the mutating endpoints use, so the prediction and
    the eventual result come from one implementation.
    """
    trip = _trip_row(db, trip_id)
    action = (payload.action or "").strip().lower()
    if action not in {"delete", "replace", "extend", "move"}:
        raise HTTPException(status_code=400, detail="action must be delete, replace, extend or move.")

    stop_day = db.execute(
        text("SELECT day_number FROM itinerary_stops WHERE id = :sid AND trip_id = :tid"),
        {"sid": stop_id, "tid": trip_id},
    ).fetchone()
    if not stop_day:
        raise HTTPException(status_code=404, detail="Stop not found")

    day_number = stop_day.day_number
    day_rows = db.execute(
        text(DAY_STOP_SELECT), {"trip_id": trip_id, "day_number": day_number}
    ).fetchall()
    target_stop = next((row for row in day_rows if row.stop_id == stop_id), None)
    if target_stop is None:
        raise HTTPException(status_code=404, detail="Stop not found on its day")

    days = []
    candidate = None
    feasible = True

    if action == "extend":
        if not payload.duration_minutes:
            raise HTTPException(status_code=400, detail="duration_minutes is required for extend.")
        variant = [
            _as_variant(row, duration_minutes=payload.duration_minutes)
            if row.place_id == target_stop.place_id else row
            for row in day_rows
        ]
        planned = simulate_day(variant, trip, day_number, db, pinned_ids={target_stop.place_id})
        days.append(_day_preview(day_number, day_rows, planned))
        feasible = any(stop["place_id"] == target_stop.place_id for stop in planned["scheduled"])

    elif action == "delete":
        variant = [row for row in day_rows if row.place_id != target_stop.place_id]
        planned = simulate_day(variant, trip, day_number, db)
        days.append(_day_preview(day_number, day_rows, planned))

    elif action == "move":
        target_day = payload.target_day
        if not target_day:
            raise HTTPException(status_code=400, detail="target_day is required for move.")
        if not 1 <= target_day <= trip.days_count:
            raise HTTPException(status_code=400, detail=f"target_day must be between 1 and {trip.days_count}.")
        if target_day == day_number:
            raise HTTPException(status_code=400, detail="The stop is already on that day.")

        source_variant = [row for row in day_rows if row.place_id != target_stop.place_id]
        planned_source = simulate_day(source_variant, trip, day_number, db)
        days.append(_day_preview(day_number, day_rows, planned_source))

        target_rows = db.execute(
            text(DAY_STOP_SELECT), {"trip_id": trip_id, "day_number": target_day}
        ).fetchall()
        moved = _as_variant(target_stop, day_number=target_day,
                            scheduled_start=None, scheduled_end=None, is_locked=False)
        planned_target = simulate_day(target_rows + [moved], trip, target_day, db,
                                      pinned_ids={target_stop.place_id})
        days.append(_day_preview(target_day, target_rows, planned_target))
        feasible = any(stop["place_id"] == target_stop.place_id for stop in planned_target["scheduled"])

    else:  # replace
        exclude_ids, existing_names = _trip_place_names(
            db, trip_id, exclude_place_id=target_stop.place_id
        )
        exclude_ids.add(target_stop.place_id)
        origin = db.execute(text("""
            SELECT i.day_number, l.place_id, l.name, l.primary_category, l.time_slot,
                   ST_X(l.geom::geometry) AS lng, ST_Y(l.geom::geometry) AS lat
            FROM itinerary_stops i JOIN locations l ON i.place_id = l.place_id
            WHERE i.id = :sid
        """), {"sid": stop_id}).fetchone()
        candidates = find_replacement_candidates(db, trip.city, origin, exclude_ids, existing_names)

        if not candidates:
            feasible = False
        else:
            choice, why = choose_replacement(trip.city, target_stop.name, candidates)
            if choice is None:
                feasible = False
            else:
                candidate = {
                    "place_id": choice.place_id,
                    "place_name": choice.name,
                    "category": choice.primary_category,
                    "why": why,
                    "km_away": round(float(choice.meters) / 1000, 1),
                }
                replacement_row = _location_as_day_row(db, choice.place_id, day_number)
                variant = [row for row in day_rows if row.place_id != target_stop.place_id]
                variant.append(replacement_row)
                planned = simulate_day(variant, trip, day_number, db, pinned_ids={choice.place_id})
                days.append(_day_preview(day_number, day_rows, planned))
                feasible = any(stop["place_id"] == choice.place_id for stop in planned["scheduled"])

    return {
        "action": action,
        "stop_id": stop_id,
        "days": days,
        "candidate": candidate,
        "feasible": feasible,
        "refill_note": "After applying, any freed slot may be topped up with another place.",
    }


@router.post("/trips/{trip_id}/stops/{stop_id}/replace")
def replace_stop(trip_id: str, stop_id: str, db: Session = Depends(get_db),
                 payload: ReplaceRequest | None = None):
    """Swap one stop for a similar nearby place, chosen by the LLM."""
    trip = _trip_row(db, trip_id)
    stop = db.execute(text("""
        SELECT i.id, i.day_number, l.place_id, l.name, l.primary_category, l.time_slot,
               ST_X(l.geom::geometry) AS lng, ST_Y(l.geom::geometry) AS lat
        FROM itinerary_stops i JOIN locations l ON i.place_id = l.place_id
        WHERE i.id = :sid AND i.trip_id = :tid
    """), {"sid": stop_id, "tid": trip_id}).fetchone()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    exclude_ids, existing_names = _trip_place_names(db, trip_id, exclude_place_id=stop.place_id)
    exclude_ids.add(stop.place_id)
    candidates = find_replacement_candidates(db, trip.city, stop, exclude_ids, existing_names)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="No similar place nearby left to suggest for this stop.",
        )

    choice, why = choose_replacement(trip.city, stop.name, candidates)
    if payload and payload.place_id:
        # Reuse the candidate the preview showed, so Apply cannot surprise the user.
        picked = next((item for item in candidates if item.place_id == payload.place_id), None)
        if picked is not None:
            choice, why = picked, "Confirmed from the preview"

    if choice is None:
        raise HTTPException(status_code=404, detail=f"Could not find a replacement: {why}")

    new_stop_id = str(uuid.uuid4())
    db.execute(text("DELETE FROM itinerary_stops WHERE id = :sid"), {"sid": stop_id})
    db.execute(text("""
        INSERT INTO itinerary_stops
            (id, trip_id, place_id, day_number, status, is_locked)
        VALUES (:id, :tid, :pid, :day, 'PENDING', FALSE)
    """), {
        "id": new_stop_id,
        "tid": trip_id,
        "pid": choice.place_id,
        "day": stop.day_number,
    })
    db.commit()

    result = plan_day(trip_id, stop.day_number, trip, db, pinned_ids={choice.place_id},
                      exclude_from_refill={stop.place_id})

    if choice.place_id not in {stop_["place_id"] for stop_ in result["scheduled"]}:
        # The swap could not be placed: restore the original rather than lose the stop.
        db.execute(text("DELETE FROM itinerary_stops WHERE id = :sid"), {"sid": new_stop_id})
        db.execute(text("""
            INSERT INTO itinerary_stops
                (id, trip_id, place_id, day_number, status, is_locked)
            VALUES (:id, :tid, :pid, :day, 'PENDING', FALSE)
        """), {
            "id": str(uuid.uuid4()),
            "tid": trip_id,
            "pid": stop.place_id,
            "day": stop.day_number,
        })
        db.commit()
        plan_day(trip_id, stop.day_number, trip, db, pinned_ids={stop.place_id},
                 exclude_from_refill={choice.place_id})
        raise HTTPException(
            status_code=409,
            detail=f"'{choice.name}' could not be fitted into Day {stop.day_number}; kept the original stop.",
        )

    touch_trip(db, trip_id)
    db.commit()

    return {
        "message": f"Replaced with {choice.name}.",
        "replacement": {
            "place_name": choice.name,
            "category": choice.primary_category,
            "why": why,
            "km_away": round(float(choice.meters) / 1000, 1),
        },
        "itinerary": itinerary_payload(trip_id, db),
        "dropped": result["dropped"],
        "added": result["added"],
        "relaxed": result["relaxed"],
    }


@router.post("/trips/{trip_id}/recalculate")
def remove_and_recalculate(trip_id: str, remove_stop_id: str | None = None, db: Session = Depends(get_db)):
    trip = _trip_row(db, trip_id)
    replaced = None
    removed_day = None
    attempts = []
    blocked_place_ids = frozenset()

    if remove_stop_id:
        info = db.execute(text("""
            SELECT i.day_number, l.place_id, l.name, l.primary_category, l.time_slot,
                   l.visit_duration,
                   ST_X(l.geom::geometry) AS lng, ST_Y(l.geom::geometry) AS lat
            FROM itinerary_stops i JOIN locations l ON i.place_id = l.place_id
            WHERE i.id = :sid AND i.trip_id = :tid
        """), {"sid": remove_stop_id, "tid": trip_id}).fetchone()

        if info:
            removed_day = info.day_number
            blocked_place_ids = {info.place_id}

            exclude_ids, existing_names = _trip_place_names(db, trip_id)
            exclude_ids.add(info.place_id)
            db.execute(text("DELETE FROM itinerary_stops WHERE id = :sid"), {"sid": remove_stop_id})
            db.commit()
            candidates = find_replacement_candidates(
                db, trip.city, info, exclude_ids, existing_names
            )
            if candidates:
                choice, why = choose_replacement(trip.city, info.name, candidates)
                if choice is not None:
                    attempts.append((choice.place_id, choice.name, why))
                chosen_ids = {entry[0] for entry in attempts}
                for candidate in candidates:
                    if candidate.place_id not in chosen_ids:
                        attempts.append((
                            candidate.place_id,
                            candidate.name,
                            "nearest same-category option",
                        ))
                attempts = attempts[:2]

    dropped, added = [], []
    relaxed = False

    day_numbers = [row[0] for row in db.execute(
        text("SELECT DISTINCT day_number FROM itinerary_stops WHERE trip_id = :tid ORDER BY 1"),
        {"tid": trip_id},
    ).fetchall()]

    for day_number in day_numbers:
        if removed_day is not None and day_number == removed_day:
            continue  # handled below, together with the replacement attempts
        result = plan_day(trip_id, day_number, trip, db, exclude_from_refill=blocked_place_ids)
        dropped += result["dropped"]
        added += result["added"]
        relaxed = relaxed or result["relaxed"]

    if removed_day is not None:
        for place_id, place_name, why in attempts:
            inserted_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO itinerary_stops
                    (id, trip_id, place_id, day_number, status, is_locked)
                VALUES (:id, :tid, :pid, :day, 'PENDING', FALSE)
            """), {"id": inserted_id, "tid": trip_id, "pid": place_id, "day": removed_day})
            db.commit()

            result = plan_day(trip_id, removed_day, trip, db, pinned_ids={place_id},
                              exclude_from_refill=blocked_place_ids)
            if place_id in {stop["place_id"] for stop in result["scheduled"]}:
                replaced = {"place_name": place_name, "why": why}
                dropped += result["dropped"]
                added += result["added"]
                relaxed = relaxed or result["relaxed"]
                break

            # It could not be fitted; drop the attempt and try the next candidate.
            db.execute(text("DELETE FROM itinerary_stops WHERE id = :sid"), {"sid": inserted_id})
            db.commit()
        else:
            result = plan_day(trip_id, removed_day, trip, db, exclude_from_refill=blocked_place_ids)
            dropped += result["dropped"]
            added += result["added"]
            relaxed = relaxed or result["relaxed"]

    touch_trip(db, trip_id)
    db.commit()

    return {
        "message": "Itinerary updated dynamically.",
        "city": trip.city,
        "replacement": replaced,
        "itinerary": itinerary_payload(trip_id, db),
        "dropped": dropped,
        "added": added,
        "relaxed": relaxed,
    }
