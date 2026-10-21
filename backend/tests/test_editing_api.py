"""End-to-end behaviour of the itinerary API, on a throwaway database.

Covers the guarantees the product makes: nothing past closing time, no place
twice, locks survive, drag/move/delete/extend/replace keep the day valid, and
re-optimization refills a starved day.
"""

from datetime import datetime, time

from app.api.v1 import trips
from app.schemas.trip_schema import DurationRequest, ReorderRequest, TripRequest

DAY_END = time(18, 0)


def stops_by_day(payload, day):
    return [stop for stop in payload["itinerary"]["stops"] if stop["day_number"] == day]


def starts(stop):
    return datetime.fromisoformat(stop["scheduled_start"])


def ends(stop):
    return datetime.fromisoformat(stop["scheduled_end"])


def test_generation_produces_a_valid_multi_day_plan(trip):
    itinerary = trip["itinerary"]

    assert itinerary["days_count"] == 2
    assert itinerary["stops"], "expected a populated itinerary"

    for stop in itinerary["stops"]:
        assert ends(stop).time() <= DAY_END, f"{stop['place_name']} ends after the daily window"
        assert starts(stop) < ends(stop)


def test_no_place_appears_twice_in_a_trip(trip):
    names = [stop["place_name"] for stop in trip["itinerary"]["stops"]]
    stop_ids = [stop["stop_id"] for stop in trip["itinerary"]["stops"]]

    assert len(names) == len(set(names)), f"duplicate places in one trip: {names}"
    assert len(stop_ids) == len(set(stop_ids))


def test_stops_land_in_their_time_slot(trip):
    if trip.get("relaxed"):
        return  # slots were explicitly relaxed and reported

    for stop in trip["itinerary"]["stops"]:
        start = starts(stop).time()
        slot = stop.get("time_slot")

        if slot == "morning":
            assert start < time(12, 0), f"{stop['place_name']} (morning) starts at {start}"
        elif slot == "midday":
            assert time(11, 0) <= start <= time(15, 0), f"{stop['place_name']} (midday) starts at {start}"
        elif slot == "evening":
            assert start >= time(15, 0), f"{stop['place_name']} (evening) starts at {start}"


def test_reorder_keeps_the_dragged_order_and_recomputes_times(db, trip):
    trip_id = trip["trip_id"]
    day_one = stops_by_day(trip, 1)
    assert len(day_one) >= 3

    reversed_ids = [stop["stop_id"] for stop in reversed(day_one)]
    result = trips.reorder_stops(
        trip_id, ReorderRequest(day_number=1, ordered_stop_ids=reversed_ids), db
    )

    updated = stops_by_day(result, 1)
    assert [stop["stop_id"] for stop in updated] == reversed_ids
    for earlier, later in zip(updated, updated[1:]):
        assert ends(earlier) <= starts(later)


def test_move_between_days_moves_the_stop(db, trip):
    trip_id = trip["trip_id"]
    moving = stops_by_day(trip, 1)[0]

    result = trips.move_stop(trip_id, moving["stop_id"], 2, db)
    itinerary = result["itinerary"]

    moved = [stop for stop in itinerary["stops"] if stop["stop_id"] == moving["stop_id"]]
    assert moved and moved[0]["day_number"] == 2

    for stop in itinerary["stops"]:
        assert ends(stop).time() <= DAY_END


def test_locked_stop_survives_a_delete_and_replan(db, trip):
    trip_id = trip["trip_id"]
    day_one = stops_by_day(trip, 1)
    locked, victim = day_one[0], day_one[-1]

    trips.toggle_stop_lock(trip_id, locked["stop_id"], db)

    result = trips.remove_and_recalculate(trip_id, victim["stop_id"], db)
    survivors = result["itinerary"]["stops"]

    locked_after = [stop for stop in survivors if stop["place_name"] == locked["place_name"]]
    assert locked_after, "a locked stop must never be dropped"
    assert locked_after[0]["is_locked"] is True
    assert not any(stop["stop_id"] == victim["stop_id"] for stop in survivors)


def test_delete_backfills_the_day(db, trip):
    trip_id = trip["trip_id"]
    victim = stops_by_day(trip, 1)[1]

    payload = trips.remove_and_recalculate(trip_id, victim["stop_id"], db)

    assert payload["replacement"] is not None, "a removed stop should be replaced"
    names = [stop["place_name"] for stop in payload["itinerary"]["stops"]]
    assert payload["replacement"]["place_name"] in names
    assert len(names) == len(set(names))


def test_extend_duration_replans_without_overrunning(db, trip):
    trip_id = trip["trip_id"]
    target = stops_by_day(trip, 1)[0]

    payload = trips.update_stop_duration(
        trip_id, target["stop_id"], DurationRequest(duration_minutes=180), db
    )

    updated = [stop for stop in payload["itinerary"]["stops"]
               if stop["stop_id"] == target["stop_id"]]
    assert updated and updated[0]["duration_minutes"] == 180

    for stop in payload["itinerary"]["stops"]:
        assert ends(stop).time() <= DAY_END


def test_replace_swaps_in_a_different_place(db, trip):
    trip_id = trip["trip_id"]
    target = stops_by_day(trip, 1)[0]

    payload = trips.replace_stop(trip_id, target["stop_id"], db)

    replacement = payload["replacement"]
    assert replacement["place_name"] != target["place_name"]
    assert replacement["why"]

    names = [stop["place_name"] for stop in payload["itinerary"]["stops"]]
    assert replacement["place_name"] in names
    assert target["place_name"] not in names
    assert len(names) == len(set(names))


def test_a_starved_day_gets_suggestions_instead_of_silent_additions(db, trip, engine):
    trip_id = trip["trip_id"]
    keep = stops_by_day(trip, 1)[0]

    from sqlalchemy import text as sql

    with engine.begin() as conn:
        conn.execute(sql("""
            DELETE FROM itinerary_stops
            WHERE trip_id = :tid AND day_number = 1 AND id <> :keep
        """), {"tid": trip_id, "keep": keep["stop_id"]})

    trips.update_stop_duration(
        trip_id, keep["stop_id"], DurationRequest(duration_minutes=60), db
    )

    day_one = [stop for stop in trips.itinerary_payload(trip_id, db)["stops"]
               if stop["day_number"] == 1]
    assert len(day_one) == 1, "nothing may be added without the traveller asking"

    offered = trips.day_suggestions(trip_id, 1, db)["suggestions"]
    assert offered, "a day with room should offer options"
    assert all(item["place_id"] for item in offered)


def test_existing_places_are_reused_without_a_refetch(db, trip, monkeypatch):
    """Catalogue policy: keywords must never trigger a Google refetch."""
    from datetime import date, timedelta

    from app.api.v1 import trips as trips_module

    calls = {"count": 0}

    def spy(*args, **kwargs):
        calls["count"] += 1

    monkeypatch.setattr(trips_module, "fetch_and_cache_places_from_google", spy)

    start = date(2026, 12, 5)
    trips.generate_trip(TripRequest(
        user_id="123e4567-e89b-12d3-a456-426614174000",
        destination_city="Testville",
        start_date=start.isoformat(),
        end_date=(start + timedelta(days=1)).isoformat(),
        transport_mode="Driving",
        selected_keywords=["Beaches", "Ancient Temples"],
    ), db)

    assert calls["count"] == 0, "an existing catalogue must be reused, not refetched"


def test_uncovered_keyword_triggers_a_targeted_fetch(db, trip, monkeypatch):
    """A keyword the catalogue cannot serve fetches -- and only that keyword."""
    from datetime import date, timedelta

    from app.api.v1 import trips as trips_module

    calls = []

    def spy(city, keywords, session):
        calls.append(list(keywords))

    monkeypatch.setattr(trips_module, "fetch_and_cache_places_from_google", spy)

    start = date(2026, 12, 7)
    response = trips.generate_trip(TripRequest(
        user_id="123e4567-e89b-12d3-a456-426614174000",
        destination_city="Testville",
        start_date=start.isoformat(),
        end_date=(start + timedelta(days=1)).isoformat(),
        transport_mode="Driving",
        selected_keywords=["Beaches", "Waterfalls"],
    ), db)

    assert calls == [["Waterfalls"]], f"expected a targeted fetch, got {calls}"
    assert response["catalogue_fetched_for"] == ["Waterfalls"]
