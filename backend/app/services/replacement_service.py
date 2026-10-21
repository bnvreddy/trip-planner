"""Pick a thematically similar replacement for a stop the traveller removed.

SQL narrows the field (same city, unused, nearby, decent rating), then Gemini
ranks what is left and explains the pick. Any failure degrades to the nearest
same-category candidate -- never to "highest rated anywhere in the city", which
is what produced a five-temple day.
"""

import json

from sqlalchemy import text

from app.services.dedupe_service import names_likely_same
from app.services.llm_service import ai_client, model_text

DEFAULT_RADIUS_METERS = 8000


def find_replacement_candidates(db, city, origin, exclude_ids, existing_names=None,
                                radius_meters=DEFAULT_RADIUS_METERS, limit=12):
    """Nearby, unused, reasonably rated places -- same category first."""
    existing_names = existing_names or []
    rows = db.execute(
        text("""
            SELECT l.place_id, l.name, l.primary_category, l.category_tags, l.rating,
                   COALESCE(l.visit_duration, 90) AS visit_duration,
                   ST_Y(l.geom::geometry) AS lat, ST_X(l.geom::geometry) AS lng,
                   ST_Distance(
                       l.geom::geography,
                       ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                   ) AS meters
            FROM locations l
            WHERE l.city = :city
              AND l.place_id <> ALL(:exclude)
              AND COALESCE(l.rating, 0) >= 4.0
              AND ST_DWithin(
                    l.geom::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius
                  )
            ORDER BY (l.time_slot = :slot) DESC, (l.primary_category = :category) DESC, meters ASC
            LIMIT :limit
        """),
        {
            "city": city,
            "lng": float(origin.lng),
            "lat": float(origin.lat),
            "exclude": list(exclude_ids) or [""],
            "category": origin.primary_category,
            "slot": getattr(origin, "time_slot", None),
            "radius": radius_meters,
            "limit": limit,
        },
    ).fetchall()

    # Never suggest a second version of a place already on the trip.
    return [
        row for row in rows
        if not any(names_likely_same(row.name, name) for name in existing_names)
    ]


def choose_replacement(city, removed_name, candidates, keywords=None):
    """Return ``(candidate_row, why)`` or ``(None, reason)``."""
    if not candidates:
        return None, "no nearby alternative left"

    fallback = candidates[0]
    fallback_reason = "Closest same-category option that still fits the day"

    if not ai_client:
        return fallback, fallback_reason

    payload = [
        {
            "place_id": row.place_id,
            "name": row.name,
            "category": row.primary_category,
            "tags": row.category_tags,
            "rating": row.rating,
            "km_away": round(float(row.meters) / 1000, 1),
        }
        for row in candidates
    ]

    prompt = f"""
    You are a local travel planner in {city}.
    The traveller removed "{removed_name}" from their itinerary and wants a
    similar nearby substitute. Their stated interests: {keywords or "not specified"}.

    Candidates:
    {json.dumps(payload)}

    Pick exactly one candidate that best replaces the removed place in theme and
    convenience. Return JSON: {{"place_id": "<id>", "why": "<max 20 words>"}}
    """

    try:
        response = ai_client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": 0.3},
        )
        parsed = json.loads(model_text(response))
        chosen_id = parsed.get("place_id")
        why = (parsed.get("why") or "").strip() or fallback_reason

        for row in candidates:
            if row.place_id == chosen_id:
                return row, why
        return fallback, fallback_reason
    except Exception as exc:  # noqa: BLE001
        print(f"Gemini replacement ranking failed ({type(exc).__name__}: {exc}); using nearest")
        return fallback, fallback_reason
