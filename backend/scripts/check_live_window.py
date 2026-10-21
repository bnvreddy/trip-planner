"""Read-only verification against the trips already in the database.

Prints, per trip-day: how the stored schedule behaves versus what the fixed
planner produces from the same stops. Writes nothing to itinerary_stops.

    python -m scripts.check_live_window
"""

from sqlalchemy import text

from app.api.v1.trips import DAY_STOP_SELECT, build_day_inputs, trip_window
from app.db.database import engine
from app.services.distance_matrix import get_or_fetch_distance_matrix
from app.services.routing_service import solve_trip_routing


def minutes(value):
    return value.hour * 60 + value.minute


def main():
    with engine.connect() as conn:
        trips = conn.execute(text("""
            SELECT id, city, days_count, start_date, transport_mode, day_start_time, day_end_time
            FROM trips ORDER BY start_date
        """)).fetchall()

        for trip in trips:
            day_start, day_end = trip_window(trip)
            print(f"\n=== {trip.city} ({trip.start_date}, {trip.days_count} days) "
                  f"window {day_start // 60:02d}:{day_start % 60:02d}-{day_end // 60:02d}:{day_end % 60:02d} ===")

            for day in range(1, trip.days_count + 1):
                stored = conn.execute(text("""
                    SELECT l.name, i.scheduled_end, i.duration_minutes, l.visit_duration
                    FROM itinerary_stops i JOIN locations l ON i.place_id = l.place_id
                    WHERE i.trip_id = :tid AND i.day_number = :day
                    ORDER BY i.scheduled_start
                """), {"tid": trip.id, "day": day}).fetchall()

                if not stored:
                    continue

                overruns = [row for row in stored if minutes(row.scheduled_end) > day_end]
                print(f"  day {day}: {len(stored)} stops, "
                      f"stored last end {max(minutes(r.scheduled_end) for r in stored) // 60:02d}:"
                      f"{max(minutes(r.scheduled_end) for r in stored) % 60:02d}, "
                      f"{len(overruns)} past the window")

                rows = conn.execute(text(DAY_STOP_SELECT), {"trip_id": trip.id, "day_number": day}).fetchall()
                locations, durations, dropped = build_day_inputs(rows, day_start, day_end)
                if not locations:
                    continue

                matrix = get_or_fetch_distance_matrix(
                    locations, (trip.transport_mode or "driving").lower(), conn
                )
                route = solve_trip_routing(locations, matrix, durations)

                if route:
                    last = max(stop["departure_minute"] for stop in route)
                    unplaced = len(locations) - len(route)
                    print(f"        re-planned: {len(route)} stops, last end "
                          f"{last // 60:02d}:{last % 60:02d}, {len(dropped)} unfit + "
                          f"{unplaced} dropped by the solver")
                else:
                    print("        re-planned: no feasible route")

                for item in dropped:
                    print(f"        dropped: {item['place_name']} ({item['reason']})")


if __name__ == "__main__":
    main()
