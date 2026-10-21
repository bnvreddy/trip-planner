"""How long a visit actually takes.

One number cannot fit every place: a shrine is a 40-minute stop, a zoo is three
hours. Durations are assigned per place by the LLM (cached in
``locations.visit_duration``) with category ranges as both prompt guidance and
fallback. A user's per-stop override still takes precedence downstream.
"""

import json

from sqlalchemy import text

from app.services.llm_service import ai_client, model_text

# Sane ranges per category, in minutes. Also used to sanity-check LLM output.
DURATION_RANGES = {
    "hindu_temple": (30, 60),
    "church": (30, 45),
    "mosque": (30, 45),
    "place_of_worship": (30, 60),
    "museum": (60, 120),
    "art_gallery": (45, 90),
    "zoo": (120, 240),
    "aquarium": (60, 90),
    "amusement_park": (180, 300),
    "water_park": (120, 240),
    "park": (45, 75),
    "beach": (60, 120),
    "nature_preserve": (60, 120),
    "botanical_garden": (45, 90),
    "viewpoint": (20, 45),
    "mountain_peak": (60, 120),
    "market": (45, 75),
    "shopping_mall": (60, 120),
    "restaurant": (60, 90),
    "cafe": (45, 60),
    "bridge": (20, 30),
    "wildlife_park": (120, 180),
}
DEFAULT_RANGE = (45, 90)

NAME_HINTS = (
    ("beach", (60, 120)),
    ("temple", (30, 60)),
    ("devasthanam", (30, 60)),
    ("matha", (30, 45)),
    ("museum", (60, 120)),
    ("zoo", (120, 240)),
    ("park", (45, 75)),
    ("garden", (45, 90)),
    ("falls", (60, 90)),
    ("caves", (45, 75)),
)


def _range_for(primary_category, name, tags=None):
    if primary_category in DURATION_RANGES:
        return DURATION_RANGES[primary_category]

    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = []
    for tag in tags or []:
        if tag in DURATION_RANGES:
            return DURATION_RANGES[tag]

    lowered = (name or "").lower()
    for hint, bounds in NAME_HINTS:
        if hint in lowered:
            return bounds

    return DEFAULT_RANGE


def _round_to_quarter(minutes: int) -> int:
    return max(15, int(round(minutes / 15.0) * 15))


def rule_duration(primary_category: str, name: str, tags=None) -> int:
    """Deterministic midpoint of the category range."""
    low, high = _range_for(primary_category, name, tags)
    return _round_to_quarter((low + high) / 2)


def classify_city_durations(db, city: str, batch_size: int = 40) -> int:
    """Assign visit lengths to places that only have the ingest default."""
    rows = db.execute(
        text("""
            SELECT place_id, name, primary_category, category_tags, visit_duration, duration_source
            FROM locations
            WHERE city = :city
              AND (duration_source IS NULL OR duration_source IN ('default', 'rule'))
        """),
        {"city": city},
    ).fetchall()
    if not rows:
        return 0

    assigned = {}
    for start in range(0, len(rows), batch_size):
        assigned.update(_classify_batch(city, rows[start:start + batch_size]))

    for row in rows:
        minutes = assigned.get(row.place_id)
        if not minutes:
            minutes = rule_duration(row.primary_category, row.name, row.category_tags)
            source = "rule"
        else:
            source = "llm"

        db.execute(
            text("""
                UPDATE locations
                SET visit_duration = :minutes, duration_source = :source
                WHERE place_id = :pid
            """),
            {"minutes": minutes, "source": source, "pid": row.place_id},
        )
    db.commit()
    return len(rows)


def _classify_batch(city: str, batch) -> dict:
    fallback = {
        row.place_id: rule_duration(row.primary_category, row.name, row.category_tags)
        for row in batch
    }
    if not ai_client:
        return fallback

    payload = []
    for row in batch:
        low, high = _range_for(row.primary_category, row.name, row.category_tags)
        payload.append({
            "place_id": row.place_id,
            "name": row.name,
            "category": row.primary_category,
            "tags": row.category_tags,
            "expected_minutes_range": [low, high],
        })

    prompt = f"""
    You are a local guide in {city}. Estimate how long a typical visitor spends
    at each place, in whole minutes, staying inside its expected range.

    Rules of thumb: shrines and viewpoints are short stops; museums and markets
    take longer; beaches, zoos and amusement parks take the longest. Prefer
    round numbers (30, 45, 60, 90, 120, 180, 240).

    Places:
    {json.dumps(payload)}

    Return JSON: {{"durations": [{{"place_id": "<id>", "minutes": <int>}}]}}
    """

    try:
        response = ai_client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": 0.2},
        )
        parsed = json.loads(model_text(response))
        entries = parsed.get("durations", []) if isinstance(parsed, dict) else []

        resolved = dict(fallback)
        bounds_by_id = {
            row.place_id: _range_for(row.primary_category, row.name, row.category_tags)
            for row in batch
        }
        for entry in entries:
            place_id = entry.get("place_id")
            minutes = entry.get("minutes")
            if place_id not in bounds_by_id or not isinstance(minutes, (int, float)):
                continue
            low, high = bounds_by_id[place_id]
            resolved[place_id] = _round_to_quarter(min(high, max(low, minutes)))
        return resolved
    except Exception as exc:  # noqa: BLE001 - durations must never block a trip
        print(f"Duration classification failed ({type(exc).__name__}: {exc}); using category rules")
        return fallback
