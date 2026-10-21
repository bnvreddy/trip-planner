"""Day planning: the LLM decides, arithmetic only verifies.

The model is good at "temples first, beach at sunset, museum at midday" and bad
at adding minutes. So it produces the order and start times, this module checks
the sums, and a deterministic fallback guarantees a usable day either way.
"""

import json

from app.services.distance_matrix import estimate_minutes
from app.services.llm_service import ai_client, model_text
from app.services.slot_service import rule_slot

BAND_ORDER = ("morning", "midday", "afternoon", "flexible", "evening")
TRAVEL_BUFFER_MINUTES = 5
DEFAULT_LEG_MINUTES = 10  # used when a caller has no coordinates (band balancing)


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _to_minutes(value: str) -> int:
    hours, minutes = str(value).split(":")[:2]
    return int(hours) * 60 + int(minutes)


def band_of(loc) -> str:
    return loc.get("slot") or rule_slot(loc.get("primary_category"), loc.get("name", ""))


def travel_between(a, b, mode="driving") -> int:
    if not a or not b:
        return 0
    if not all(key in a for key in ("lat", "lng")) or not all(key in b for key in ("lat", "lng")):
        return DEFAULT_LEG_MINUTES
    return estimate_minutes(a, b, mode)


def verify_schedule(schedule, locations_by_id, durations, day_start, day_end, mode="driving"):
    """Plain arithmetic. Returns human-readable violations, empty when it holds."""
    problems = []
    previous_loc = None
    previous_departure = None

    if not schedule:
        return ["nothing is scheduled"]

    for index, stop in enumerate(schedule):
        loc = locations_by_id.get(stop["place_id"])
        if loc is None:
            problems.append(f"{stop.get('name', 'a stop')} is no longer in the catalogue")
            continue

        duration = durations.get(stop["place_id"], 60)
        arrival = stop["arrival_minute"]
        departure = arrival + duration
        window_start, window_end = loc.get("time_window", (day_start, day_end))
        label = loc.get("name", "a stop")

        if arrival < day_start:
            problems.append(f"{label} starts before {_hhmm(day_start)}")
        if arrival < window_start:
            problems.append(
                f"{label} starts at {_hhmm(arrival)}, before its {band_of(loc)} window "
                f"opens at {_hhmm(window_start)}"
            )
        if arrival > window_end - duration:
            problems.append(
                f"{label} cannot start at {_hhmm(arrival)}: a {duration}-minute visit "
                f"would run past {_hhmm(window_end)}"
            )
        if departure > day_end:
            problems.append(f"the day ends at {_hhmm(departure)}, past your {_hhmm(day_end)} limit")

        if previous_loc is not None:
            leg = travel_between(previous_loc, loc, mode)
            needed = previous_departure + leg
            if arrival < needed:
                problems.append(
                    f"there is no time to get from {previous_loc['name']} to {label}: "
                    f"{leg} min drive, but only {arrival - previous_departure} min between them"
                )
        previous_loc = loc
        previous_departure = departure

    seen = [stop["place_id"] for stop in schedule]
    if len(seen) != len(set(seen)):
        problems.append("a place appears twice on the same day")

    return problems


def sequence_by_band(locations, durations, day_start, day_end, mode="driving"):
    """Deterministic fallback: morning → midday → flexible → evening, real travel.

    Returns ``(schedule, unplaced)``; unplaced entries carry a plain reason.
    """
    ordered = sorted(
        locations,
        key=lambda loc: (
            BAND_ORDER.index(band_of(loc)) if band_of(loc) in BAND_ORDER else 3,
            # Inside a band, a locked stop gets the first slot, exactly like the
            # undroppable penalty used to guarantee.
            0 if loc.get("is_locked") else 1,
            loc.get("time_window", (day_start, day_end))[0],
        ),
    )

    schedule = []
    unplaced = []
    clock = day_start
    previous = None

    for loc in ordered:
        duration = durations[loc["place_id"]]
        window_start, window_end = loc.get("time_window", (day_start, day_end))
        leg = travel_between(previous, loc, mode) if previous else 0
        arrival = max(clock + leg, window_start)
        latest = min(window_end - duration, day_end - duration)

        if arrival > latest:
            unplaced.append({
                "place_name": loc["name"],
                "reason": (
                    f"the {band_of(loc)} window is taken: {_hhmm(clock)} is already booked "
                    f"and the window closes at {_hhmm(window_end)}"
                ),
                "needed_minutes": duration,
                "free_minutes": max(0, latest - max(clock + leg, window_start)),
                "slot": band_of(loc),
            })
            continue

        schedule.append({
            "place_id": loc["place_id"],
            "name": loc["name"],
            "arrival_minute": arrival,
            "departure_minute": arrival + duration,
        })
        clock = arrival + duration
        previous = loc

    return schedule, unplaced


def _plan_payload(locations, durations, day_start, day_end, mode):
    """The compact table the model reasons over."""
    rows = []
    for loc in locations:
        window_start, window_end = loc.get("time_window", (day_start, day_end))
        rows.append({
            "place_id": loc["place_id"],
            "name": loc["name"],
            "visit_minutes": durations[loc["place_id"]],
            "band": band_of(loc),
            "allowed_window": f"{_hhmm(window_start)}-{_hhmm(window_end)}",
        })
    return rows


def _travel_table(locations, mode):
    table = {}
    for a in locations:
        for b in locations:
            if a["place_id"] != b["place_id"]:
                table[f"{a['place_id']}|{b['place_id']}"] = travel_between(a, b, mode)
    return table


def _ask_model(locations, durations, day_start, day_end, mode, city, problems=None):
    payload = _plan_payload(locations, durations, day_start, day_end, mode)
    travel = _travel_table(locations, mode)

    revision = ""
    if problems:
        revision = (
            "\nYour previous plan did not work. Fix exactly these problems:\n- "
            + "\n- ".join(problems)
            + "\n"
        )

    prompt = f"""
    You are planning one day of a trip{f' in {city}' if city else ''}.
    Day runs {_hhmm(day_start)}-{_hhmm(day_end)}.

    Places (visit length is fixed, do not change it):
    {json.dumps(payload)}

    Minutes of driving between them: {json.dumps(travel)}

    Build the day. Rules:
    - use every place at most once,
    - each place must start inside its allowed window,
    - leave the driving time between stops,
    - the last visit must finish by {_hhmm(day_end)}.
    {revision}
    Return JSON:
    {{"order": [{{"place_id": "<id>", "start": "HH:MM"}}], "why": "one short sentence"}}
    """

    try:
        response = ai_client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": 0.2},
        )
        parsed = json.loads(model_text(response))
        entries = parsed.get("order", []) if isinstance(parsed, dict) else []

        by_id = {loc["place_id"]: loc for loc in locations}
        schedule = []
        for entry in entries:
            place_id = entry.get("place_id")
            start = entry.get("start")
            if place_id not in by_id or not isinstance(start, str):
                continue
            arrival = _to_minutes(start)
            schedule.append({
                "place_id": place_id,
                "name": by_id[place_id]["name"],
                "arrival_minute": arrival,
                "departure_minute": arrival + durations[place_id],
            })

        if not schedule:
            return None, problems
        return schedule, problems
    except Exception as exc:  # noqa: BLE001 - the fallback is always available
        print(f"Day planning call failed ({type(exc).__name__}: {exc}); using the calculator")
        return None, problems


def plan_day(locations, durations, day_start, day_end, city=None, mode="driving", allow_llm=True):
    """Plan one day. LLM first, one revision, then the deterministic fallback."""
    if not locations:
        return {"scheduled": [], "unplaced": [], "source": "empty", "problems": []}

    locations_by_id = {loc["place_id"]: loc for loc in locations}
    fallback_schedule, fallback_unplaced = sequence_by_band(
        locations, durations, day_start, day_end, mode
    )

    if not allow_llm or ai_client is None or len(locations) < 2:
        return {
            "scheduled": fallback_schedule,
            "unplaced": fallback_unplaced,
            "source": "calculator",
            "problems": [],
        }

    schedule, _ = _ask_model(locations, durations, day_start, day_end, mode, city)
    if not schedule:
        return {
            "scheduled": fallback_schedule,
            "unplaced": fallback_unplaced,
            "source": "calculator",
            "problems": ["the planner could not produce a usable order"],
        }

    problems = verify_schedule(schedule, locations_by_id, durations, day_start, day_end, mode)
    if not problems:
        scheduled_ids = {stop["place_id"] for stop in schedule}
        return {
            "scheduled": schedule,
            "unplaced": [item for item in fallback_unplaced if item["place_name"] not in {
                locations_by_id[pid]["name"] for pid in scheduled_ids
            }],
            "source": "llm",
            "problems": [],
        }

    # One revision, with the exact arithmetic that failed.
    revised, _ = _ask_model(locations, durations, day_start, day_end, mode, city, problems)
    if revised:
        remaining = verify_schedule(revised, locations_by_id, durations, day_start, day_end, mode)
        if not remaining:
            scheduled_ids = {stop["place_id"] for stop in revised}
            return {
                "scheduled": revised,
                "unplaced": [item for item in fallback_unplaced if item["place_name"] not in {
                    locations_by_id[pid]["name"] for pid in scheduled_ids
                }],
                "source": "llm-revised",
                "problems": [],
            }

    return {
        "scheduled": fallback_schedule,
        "unplaced": fallback_unplaced,
        "source": "calculator",
        "problems": problems,
    }


def sequence_order(locations, durations, day_start, day_end, order_ids=None, mode="driving",
                   allow_overrun=False):
    """Time-stamp a caller-fixed order (drag & drop). Arithmetic only.

    With ``allow_overrun`` an explicit drag wins and nothing is set aside; the
    caller reports how far past the window the day now runs.
    """
    by_id = {loc["place_id"]: loc for loc in locations}
    ordered = [by_id[pid] for pid in order_ids if pid in by_id] if order_ids else list(locations)

    schedule = []
    unplaced = []
    clock = day_start
    previous = None

    for loc in ordered:
        duration = durations[loc["place_id"]]
        window_start, window_end = loc.get("time_window", (day_start, day_end))
        leg = travel_between(previous, loc, mode) if previous else 0
        arrival = max(clock + leg, window_start)

        if arrival + duration > min(window_end, day_end) and not allow_overrun:
            free = max(0, min(window_end, day_end) - arrival)
            unplaced.append({
                "place_name": loc["name"],
                "reason": f"needs {duration} min but only {free} min are left in its {band_of(loc)} window",
                "needed_minutes": duration,
                "free_minutes": free,
                "slot": band_of(loc),
            })
            continue

        schedule.append({
            "place_id": loc["place_id"],
            "name": loc["name"],
            "arrival_minute": arrival,
            "departure_minute": arrival + duration,
        })
        clock = arrival + duration
        previous = loc

    return schedule, unplaced


def band_capacity(locations, durations, day_start, day_end, mode="driving") -> dict:
    """How many stops each band can actually hold, given real visit lengths."""
    schedule, unplaced = sequence_by_band(locations, durations, day_start, day_end, mode)
    counts = {}
    for stop in schedule:
        loc = next(item for item in locations if item["place_id"] == stop["place_id"])
        counts[band_of(loc)] = counts.get(band_of(loc), 0) + 1
    return counts


def _haversine_km(a, b) -> float:
    import math

    radius = 6371.0
    lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
    d_lat = lat2 - lat1
    d_lng = math.radians(b["lng"] - a["lng"])
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def _nearest_neighbour_chain(points):
    """Order points so each is close to the previous one (a greedy tour).

    Start from the most south-western point for a stable, repeatable chain.
    """
    remaining = list(points)
    if not remaining:
        return []
    start = min(remaining, key=lambda p: (p["lat"], p["lng"]))
    chain = [start]
    remaining.remove(start)
    while remaining:
        last = chain[-1]
        nxt = min(remaining, key=lambda p: _haversine_km(last, p))
        chain.append(nxt)
        remaining.remove(nxt)
    return chain


def cluster_by_location(places, days_count):
    """Split places into ``days_count`` geographically tight day-groups.

    The headline bug was one day scattered across the whole city. Grouping by
    time-slot capacity caused it. Instead we walk a nearest-neighbour chain and
    cut it into balanced, contiguous segments, so every day is one compact area
    while keeping days roughly even in size.

    ``places`` need ``place_id``, ``lat`` and ``lng``. Returns
    ``{"day_1": [place_id, ...], ...}``.
    """
    grouped = {f"day_{day}": [] for day in range(1, max(1, days_count) + 1)}
    usable = [p for p in places if p.get("lat") is not None and p.get("lng") is not None]
    if not usable:
        return grouped

    chain = _nearest_neighbour_chain(usable)
    days_count = max(1, days_count)

    total = len(chain)
    base, extra = divmod(total, days_count)
    index = 0
    for day in range(days_count):
        size = base + (1 if day < extra else 0)
        for place in chain[index:index + size]:
            grouped[f"day_{day + 1}"].append(place["place_id"])
        index += size

    return grouped
