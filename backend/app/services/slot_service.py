"""Where in the day a place belongs.

Distance alone will happily park a beach at 09:00 because it is five minutes
away. Each place therefore carries a ``time_slot`` decided by the LLM (cached in
the database) with deterministic category rules as the fallback, and the
optimizer intersects it with opening hours and the traveller's daily window.
"""

import json

from sqlalchemy import text

from app.services.llm_service import ai_client, model_text

# Slots are proportional to the traveller's day, not fixed clock times: with a
# 09:00-18:00 day the evening starts around 15:30, with a 09:00-21:00 day it
# starts at 18:00. Fixed windows used to squeeze every evening place into two
# hours and then report "doesn't fit" while the day was half empty.
SLOT_PROPORTIONS = {
    "morning": (0.00, 0.40),
    "midday": (0.25, 0.65),
    "afternoon": (0.45, 0.85),
    "evening": (0.62, 1.00),
    "flexible": (0.00, 1.00),
}

# The evening keeps at least the last three hours when the day is long.
MIN_EVENING_MINUTES = 180

VALID_SLOTS = ("morning", "midday", "afternoon", "evening", "flexible")
DEFAULT_SLOT = "flexible"

# Search tags are more granular than primary_category, so both are consulted.
TAG_SLOT_RULES = {
    "hindu_temple": "morning",
    "church": "morning",
    "mosque": "morning",
    "synagogue": "morning",
    "place_of_worship": "morning",
    "mountain_peak": "morning",
    "wildlife_park": "morning",
    "museum": "midday",
    "art_gallery": "midday",
    "zoo": "midday",
    "aquarium": "midday",
    "cafe": "midday",
    "water_park": "midday",
    "shopping_mall": "afternoon",
    "park": "evening",
    "beach": "evening",
    "nature_preserve": "evening",
    "botanical_garden": "evening",
    "viewpoint": "evening",
    "fishing_pier": "evening",
    "market": "evening",
    "restaurant": "evening",
    "bridge": "evening",
}

NAME_HINTS = (
    ("beach", "evening"),
    ("temple", "morning"),
    ("matha", "morning"),
    ("devasthanam", "morning"),
    ("church", "morning"),
    ("museum", "midday"),
    ("park", "evening"),
    ("garden", "evening"),
    ("lake", "evening"),
    ("island", "evening"),
)


def rule_slot(primary_category: str, name: str, tags=None) -> str:
    """Deterministic fallback, also used to sanity-check LLM output."""
    lowered_name = (name or "").lower()

    if primary_category in TAG_SLOT_RULES:
        return TAG_SLOT_RULES[primary_category]

    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = []
    for tag in tags or []:
        if tag in TAG_SLOT_RULES:
            return TAG_SLOT_RULES[tag]

    for hint, slot in NAME_HINTS:
        if hint in lowered_name:
            return slot

    return DEFAULT_SLOT


def slot_window(slot: str, day_start: int, day_end: int):
    """The slot clipped to the traveller's day, or None if it never overlaps."""
    span = max(1, day_end - day_start)
    low, high = SLOT_PROPORTIONS.get(slot, SLOT_PROPORTIONS[DEFAULT_SLOT])

    start = day_start + int(span * low)
    end = day_start + int(span * high)

    if slot == "morning":
        start = day_start
        end = min(end, day_start + 180)
    elif slot == "evening":
        start = max(start, day_end - MIN_EVENING_MINUTES)
        end = day_end

    start = max(day_start, min(start, day_end))
    end = max(day_start, min(end, day_end))

    if end - start < 15:
        return None
    return start, end


def classify_city_slots(db, city: str, batch_size: int = 40) -> int:
    """Assign slots to places that have none yet. Idempotent and cached."""
    rows = db.execute(
        text("""
            SELECT place_id, name, primary_category, category_tags,
                   rating, user_ratings_total
            FROM locations
            WHERE city = :city AND (time_slot IS NULL OR time_slot = '')
        """),
        {"city": city},
    ).fetchall()
    if not rows:
        return 0

    assigned = {}

    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        assigned.update(_classify_batch(city, batch))

    for row in rows:
        slot = assigned.get(row.place_id)
        if slot not in VALID_SLOTS:
            slot = rule_slot(row.primary_category, row.name, row.category_tags)
        db.execute(
            text("UPDATE locations SET time_slot = :slot WHERE place_id = :pid"),
            {"slot": slot, "pid": row.place_id},
        )
    db.commit()

    return len(rows)


def _classify_batch(city: str, batch) -> dict:
    """One LLM call per batch, falling back to rules for anything unanswered."""
    fallback = {
        row.place_id: rule_slot(row.primary_category, row.name, row.category_tags)
        for row in batch
    }
    if not ai_client:
        return fallback

    payload = [
        {
            "place_id": row.place_id,
            "name": row.name,
            "category": row.primary_category,
            "tags": row.category_tags,
        }
        for row in batch
    ]

    prompt = f"""
    You are a local guide in {city}. Decide the best time of day to visit each place.

    Rules of thumb: temples and shrines early (morning); museums, galleries and
    indoor exhibits around midday; parks, beaches, gardens, viewpoints and
    sunset spots in the evening; markets and food streets in the evening;
    anything without a clear preference is "flexible".

    Allowed values: morning, midday, afternoon, evening, flexible.

    Places:
    {json.dumps(payload)}

    Return JSON: {{"assignments": [{{"place_id": "<id>", "slot": "<value>"}}]}}
    """

    try:
        response = ai_client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": 0.2},
        )
        parsed = json.loads(model_text(response))
        entries = parsed.get("assignments", []) if isinstance(parsed, dict) else []

        resolved = dict(fallback)
        for entry in entries:
            place_id = entry.get("place_id")
            slot = (entry.get("slot") or "").strip().lower()
            if place_id in resolved and slot in VALID_SLOTS:
                resolved[place_id] = slot
        return resolved
    except Exception as exc:  # noqa: BLE001 - classification must never block a trip
        print(f"Slot classification failed ({type(exc).__name__}: {exc}); using category rules")
        return fallback
