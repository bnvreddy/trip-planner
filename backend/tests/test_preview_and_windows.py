"""Previews, per-day windows, and place-based durations.

A preview must be free of side effects and must predict what Apply then does;
per-day windows must actually bind each day separately.
"""

from datetime import date, timedelta

from sqlalchemy import text as sql

from app.api.v1 import trips
from app.schemas.trip_schema import DayWindow, PreviewRequest, TripRequest
from app.services.duration_service import rule_duration

CITY = "Testville"


def snapshot(db, trip_id):
    rows = db.execute(sql("""
        SELECT id, scheduled_start, scheduled_end, day_number
        FROM itinerary_stops WHERE trip_id = :tid ORDER BY id
    """), {"tid": trip_id}).fetchall()
    return [(row.id, str(row.scheduled_start), str(row.scheduled_end), row.day_number) for row in rows]


def stops_by_day(payload, day):
    return [stop for stop in payload["itinerary"]["stops"] if stop["day_number"] == day]


def test_preview_has_no_side_effects(db, trip):
    trip_id = trip["trip_id"]
    target = stops_by_day(trip, 1)[0]
    before = snapshot(db, trip_id)

    preview = trips.preview_stop_change(
        trip_id, target["stop_id"], PreviewRequest(action="delete"), db
    )

    assert preview["days"], "a delete preview must describe the affected day"
    assert any(
        change["action"] == "remove" and change["place_name"] == target["place_name"]
        for change in preview["days"][0]["changes"]
    )
    assert snapshot(db, trip_id) == before, "a preview must not write anything"


def test_preview_then_apply_agree(db, trip):
    trip_id = trip["trip_id"]
    target = stops_by_day(trip, 1)[0]

    preview = trips.preview_stop_change(
        trip_id, target["stop_id"], PreviewRequest(action="delete"), db
    )
    predicted = {
        change["place_name"]: change["to"]
        for change in preview["days"][0]["changes"]
        if change["action"] == "move"
    }

    applied = trips.remove_and_recalculate(trip_id, target["stop_id"], db)
    actual = {}
    for stop in stops_by_day(applied, 1):
        actual[stop["place_name"]] = stop["scheduled_start"][11:16]

    for place_name, predicted_start in predicted.items():
        if place_name in actual:  # the replacement may have changed the day's content
            assert actual[place_name] == predicted_start


def test_preview_replace_returns_the_candidate_it_will_use(db, trip):
    trip_id = trip["trip_id"]
    target = stops_by_day(trip, 1)[0]

    preview = trips.preview_stop_change(
        trip_id, target["stop_id"], PreviewRequest(action="replace"), db
    )

    candidate = preview["candidate"]
    assert candidate is not None
    assert preview["feasible"] is True

    applied = trips.replace_stop(trip_id, target["stop_id"], db)
    assert applied["replacement"]["place_name"] == candidate["place_name"]


def test_preview_move_describes_both_days(db, trip):
    trip_id = trip["trip_id"]
    moving = stops_by_day(trip, 1)[0]

    preview = trips.preview_stop_change(
        trip_id, moving["stop_id"], PreviewRequest(action="move", target_day=2), db
    )

    assert {day["day_number"] for day in preview["days"]} == {1, 2}
    target_day = next(day for day in preview["days"] if day["day_number"] == 2)
    assert any(
        change["action"] == "add" and change["place_name"] == moving["place_name"]
        for change in target_day["changes"]
    )


def test_preview_extend_reports_the_shift(db, trip):
    trip_id = trip["trip_id"]
    target = stops_by_day(trip, 1)[0]

    preview = trips.preview_stop_change(
        trip_id, target["stop_id"],
        PreviewRequest(action="extend", duration_minutes=180), db
    )

    assert preview["feasible"] is True
    assert preview["days"][0]["changes"], "extending must visibly shift or drop something"


def test_per_day_windows_are_honoured(db):
    start = date(2026, 12, 1)
    payload = TripRequest(
        user_id="123e4567-e89b-12d3-a456-426614174000",
        destination_city=CITY,
        start_date=start.isoformat(),
        end_date=(start + timedelta(days=1)).isoformat(),
        transport_mode="Driving",
        selected_keywords=[],
        daily_start_time="09:00",
        daily_end_time="18:00",
        daily_windows=[DayWindow(start="09:00", end="12:00"), DayWindow(start="14:00", end="20:00")],
    )

    trip = trips.generate_trip(payload, db)
    itinerary = trip["itinerary"]

    for stop in stops_by_day(trip, 1):
        assert stop["scheduled_end"][11:16] <= "12:00", stop
        assert stop["scheduled_start"][11:16] >= "09:00", stop

    for stop in stops_by_day(trip, 2):
        assert stop["scheduled_start"][11:16] >= "14:00", stop
        assert stop["scheduled_end"][11:16] <= "20:00", stop

    assert itinerary["days_count"] == 2


def test_reorder_feeds_the_new_order_to_the_route(db, trip):
    """The geometry request must follow the dragged order, not the old one."""
    from app.schemas.trip_schema import ReorderRequest

    trip_id = trip["trip_id"]
    day_one = stops_by_day(trip, 1)
    assert len(day_one) >= 3

    before = trips.get_day_route_geometry(trip_id, 1, db)
    reversed_ids = [stop["stop_id"] for stop in reversed(day_one)]
    trips.reorder_stops(trip_id, ReorderRequest(day_number=1, ordered_stop_ids=reversed_ids), db)
    after = trips.get_day_route_geometry(trip_id, 1, db)

    before_order = [tuple(point) for point in before["stop_coordinates"]]
    after_order = [tuple(point) for point in after["stop_coordinates"]]

    assert after_order == list(reversed(before_order)), (
        "the route input must follow the dragged order"
    )


def test_reorder_no_longer_spends_time_on_notes(db, trip):
    """Guide notes are retired: re-plans must not wait on or carry note text."""
    from app.schemas.trip_schema import ReorderRequest

    trip_id = trip["trip_id"]
    day_one = stops_by_day(trip, 1)
    reversed_ids = [stop["stop_id"] for stop in reversed(day_one)]

    result = trips.reorder_stops(
        trip_id, ReorderRequest(day_number=1, ordered_stop_ids=reversed_ids), db
    )

    assert all(stop["guide_note"] is None for stop in result["itinerary"]["stops"])


def test_durations_are_place_based():
    temple = rule_duration("hindu_temple", "Some Temple")
    museum = rule_duration("museum", "Some Museum")
    zoo = rule_duration("zoo", "Some Zoo")
    viewpoint = rule_duration("viewpoint", "Some Lookout")

    assert viewpoint < temple < museum < zoo
    assert 30 <= temple <= 60
    assert 120 <= zoo <= 240


def test_assumed_hours_do_not_block_a_long_evening():
    """The placeholder 09:00-18:00 must not reject a visit that fits the day."""
    from app.api.v1.trips import build_day_inputs, trip_window
    from types import SimpleNamespace

    row = SimpleNamespace(
        place_id="x", name="Beach", visit_duration=150, duration_minutes=None,
        operating_hours={"open": "09:00", "close": "18:00"}, hours_source="assumed",
        time_slot="evening", is_locked=False, lat=16.5, lng=80.6,
        quality_score=0.9, primary_category="beach", rating=4.5,
    )
    trip = SimpleNamespace(day_start_time=None, day_end_time=None, day_windows=None)

    day_start, day_end = trip_window(trip, 1)
    locations, durations, dropped = build_day_inputs([row], day_start, day_end)

    assert locations, f"assumed hours should not drop it: {dropped}"
    assert durations[0] == 150
