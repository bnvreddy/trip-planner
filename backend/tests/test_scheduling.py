"""Planning invariants.

The scheduler is now: the LLM proposes, `verify_schedule` checks the arithmetic,
`sequence_by_band` is the deterministic fallback. These tests pin the guarantees
that must hold no matter which path produced the day.
"""

from types import SimpleNamespace

import pytest

from app.services.dedupe_service import collapse_near_duplicates, names_likely_same
from app.services.distance_matrix import estimate_minutes
from app.services.osrm_service import route_key
from app.services.places_service import parse_time_window
from app.services.planning_service import (
    sequence_by_band,
    sequence_order,
    verify_schedule,
)
from app.api.v1.trips import effective_duration


WINDOW = (540, 1080)  # 09:00 - 18:00, the default day


def make_location(place_id, name, window=WINDOW, band="flexible", lat=16.5, lng=80.59):
    return {
        "place_id": place_id,
        "name": name,
        "time_window": window,
        "slot": band,
        "lat": lat,
        "lng": lng,
        "quality_score": 0.9,
        "is_locked": False,
    }


def point(lat, lng):
    return {"lat": lat, "lng": lng}


def test_calculator_never_ends_a_visit_after_closing():
    locations = [make_location(f"p{i}", f"Place {i}") for i in range(5)]
    durations = {f"p{i}": 90 for i in range(5)}

    schedule, unplaced = sequence_by_band(locations, durations, *WINDOW)

    assert schedule, "something should fit"
    for stop in schedule:
        assert stop["departure_minute"] <= WINDOW[1]
    problems = verify_schedule(
        schedule, {loc["place_id"]: loc for loc in locations}, durations, *WINDOW
    )
    assert problems == []


def test_multi_hour_visits_cannot_overrun_the_day():
    locations = [make_location(f"p{i}", f"Place {i}") for i in range(4)]
    durations = {f"p{i}": 240 for i in range(4)}

    schedule, unplaced = sequence_by_band(locations, durations, *WINDOW)

    assert 1 <= len(schedule) < 4
    for stop in schedule:
        assert stop["departure_minute"] <= WINDOW[1]
    assert unplaced and all(item["reason"] for item in unplaced)
    assert all(item["needed_minutes"] == 240 for item in unplaced)


def test_band_order_starts_with_the_morning():
    """An evening place listed first must not pin the start of the day."""
    locations = [
        make_location("beach", "Beach", window=(900, 1080), band="evening"),
        make_location("temple", "Temple", window=(540, 720), band="morning"),
        make_location("museum", "Museum", window=(675, 891), band="midday"),
    ]
    durations = {"beach": 90, "temple": 45, "museum": 90}

    schedule, unplaced = sequence_by_band(locations, durations, 540, 1080)
    order = [stop["place_id"] for stop in schedule]

    assert unplaced == []
    assert order == ["temple", "museum", "beach"]


def test_closing_time_is_respected_per_place():
    locations = [
        make_location("early", "Morning only", window=(540, 660), band="morning"),
        make_location("late", "All day", window=(540, 1080), band="flexible"),
    ]
    durations = {"early": 90, "late": 90}

    schedule, _ = sequence_by_band(locations, durations, *WINDOW)
    morning = next(stop for stop in schedule if stop["place_id"] == "early")

    assert morning["departure_minute"] <= 660


def test_pinned_order_keeps_everything_and_reports_overrun():
    locations = [make_location(f"p{i}", f"Place {i}") for i in range(4)]
    durations = {f"p{i}": 180 for i in range(4)}

    schedule, unplaced = sequence_order(
        locations, durations, *WINDOW, order_ids=[f"p{i}" for i in range(4)],
        allow_overrun=True,
    )

    assert unplaced == []
    assert len(schedule) == 4
    assert max(stop["departure_minute"] for stop in schedule) > WINDOW[1]


def test_verify_catches_a_drive_that_does_not_fit():
    locations = [
        make_location("a", "A", window=(540, 1080)),
        make_location("b", "B", window=(540, 1080), lat=16.9, lng=80.9),
    ]
    durations = {"a": 60, "b": 60}
    locations_by_id = {loc["place_id"]: loc for loc in locations}

    # B starts the moment A ends, but they are far apart.
    schedule = [
        {"place_id": "a", "name": "A", "arrival_minute": 540, "departure_minute": 600},
        {"place_id": "b", "name": "B", "arrival_minute": 600, "departure_minute": 660},
    ]
    problems = verify_schedule(schedule, locations_by_id, durations, *WINDOW)

    assert any("no time to get from" in problem for problem in problems)


def test_duplicate_names_are_recognised():
    assert names_likely_same("Bhavani Island", "Bhavani Island Park")
    assert names_likely_same("Kanaka Durga Temple , Indhrakeeladhri", "Kanaka Durga Temple")
    assert names_likely_same("Sri Panakala Narasimha Swamy Temple", "Panakala Narasimha Swamy Temple")
    assert not names_likely_same("Gandhi Hill", "Bapu Museum")


def test_spelling_variants_of_one_place_are_caught():
    """Without this, one hill appeared three times: Kailasa Giri, Kailasagiri…"""
    assert names_likely_same("Kailasa Giri", "Kailasagiri Hilltop Park")
    assert names_likely_same("Kailasa Giri", "VMRDA-Kailasagiri")
    assert names_likely_same("Kailasagiri Hilltop Park", "VMRDA-Kailasagiri")
    assert not names_likely_same("Gandhi Hill", "Gandhi Park")


def test_collapse_keeps_the_best_rated_twin():
    rows = [
        SimpleNamespace(place_id="a", name="Bhavani Island", rating=4.2, lat=16.51501, lng=80.59181),
        SimpleNamespace(place_id="b", name="Bhavani Island Park", rating=4.5, lat=16.51706, lng=80.59045),
        SimpleNamespace(place_id="c", name="Gandhi Hill", rating=4.1, lat=16.52000, lng=80.62000),
    ]

    kept, dropped = collapse_near_duplicates(rows)

    assert {row.place_id for row in kept} == {"b", "c"}
    assert dropped[0]["duplicate_of"] == "Bhavani Island Park"


def test_duration_override_wins_over_place_default():
    assert effective_duration(SimpleNamespace(duration_minutes=45, visit_duration=90)) == 45
    assert effective_duration(SimpleNamespace(duration_minutes=None, visit_duration=120)) == 120
    assert effective_duration(SimpleNamespace(duration_minutes=None, visit_duration=None)) == 90


def test_time_window_parsing_falls_back_to_the_default_day():
    assert parse_time_window(None) == WINDOW
    assert parse_time_window({"open": "10:30", "close": "17:15"}) == (630, 1035)
    assert parse_time_window('{"open": "08:00", "close": "20:00"}') == (480, 1200)
    assert parse_time_window("not json") == WINDOW


def test_route_cache_key_tracks_order_and_mode():
    a = {"lat": 16.51, "lng": 80.59}
    b = {"lat": 16.52, "lng": 80.60}

    assert route_key([a, b], "driving") == route_key([a, b], "driving")
    assert route_key([a, b], "driving") != route_key([b, a], "driving")
    assert route_key([a, b], "driving") != route_key([a, b], "walking")
