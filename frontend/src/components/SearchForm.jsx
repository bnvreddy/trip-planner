import { useMemo, useState } from "react";
import { Calendar, Clock, Search, SlidersHorizontal } from "lucide-react";
import { formatWindowHint } from "../api";

function daysBetween(start, end) {
  if (!start || !end) return 0;
  const from = new Date(`${start}T00:00:00`);
  const to = new Date(`${end}T00:00:00`);
  const diff = Math.round((to - from) / 86400000) + 1;
  return diff > 0 ? diff : 0;
}

const timeInputClass =
  "block w-full px-3 py-3 text-base border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500";

export default function SearchForm({ tripData, setTripData, onNext }) {
  const [perDay, setPerDay] = useState(false);

  const dayCount = useMemo(
    () => daysBetween(tripData.start_date, tripData.end_date),
    [tripData.start_date, tripData.end_date],
  );

  // Keep a row per day, seeded from the shared window.
  const dayRows = useMemo(() => {
    const rows = [...(tripData.daily_windows ?? [])];
    for (let index = rows.length; index < dayCount; index += 1) {
      rows.push({
        start: tripData.daily_start_time,
        end: tripData.daily_end_time,
      });
    }
    return rows.slice(0, dayCount);
  }, [dayCount, tripData.daily_windows, tripData.daily_start_time, tripData.daily_end_time]);

  const updateDayRow = (index, field, value) => {
    const rows = dayRows.map((row, position) =>
      position === index ? { ...row, [field]: value } : row,
    );
    setTripData({ ...tripData, daily_windows: rows });
  };

  const togglePerDay = () => {
    const next = !perDay;
    setPerDay(next);
    if (!next) {
      // Collapsing back to one window: drop the overrides.
      setTripData({ ...tripData, daily_windows: [] });
    } else {
      setTripData({ ...tripData, daily_windows: dayRows });
    }
  };

  const dateLabel = (offset) => {
    if (!tripData.start_date) return "";
    const date = new Date(`${tripData.start_date}T00:00:00`);
    date.setDate(date.getDate() + offset);
    return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  };

  const canContinue =
    tripData.destination_city && tripData.start_date && tripData.end_date && dayCount > 0;

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white p-5 sm:p-8 rounded-2xl shadow-sm border border-gray-100">
        <h2 className="text-xl sm:text-2xl font-bold mb-5 text-gray-800">
          Where do you want to go?
        </h2>

        <div className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2" htmlFor="destination">
              Destination
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                id="destination"
                type="text"
                autoComplete="off"
                className="block w-full pl-10 pr-3 py-3 text-base border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g., Visakhapatnam, Tirupati, Araku Valley"
                value={tripData.destination_city}
                onChange={(event) =>
                  setTripData({ ...tripData, destination_city: event.target.value })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2" htmlFor="start-date">
                Start date
              </label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  id="start-date"
                  type="date"
                  className="block w-full pl-10 pr-3 py-3 text-base border border-gray-300 rounded-xl"
                  value={tripData.start_date}
                  onChange={(event) =>
                    setTripData({ ...tripData, start_date: event.target.value })
                  }
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2" htmlFor="end-date">
                End date
              </label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  id="end-date"
                  type="date"
                  min={tripData.start_date}
                  className="block w-full pl-10 pr-3 py-3 text-base border border-gray-300 rounded-xl"
                  value={tripData.end_date}
                  onChange={(event) => setTripData({ ...tripData, end_date: event.target.value })}
                />
              </div>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between gap-3 mb-2">
              <span className="text-sm font-medium text-gray-700 inline-flex items-center gap-1.5">
                <Clock className="h-4 w-4 text-gray-400" />
                Daily time
              </span>
              {dayCount > 1 && (
                <button
                  type="button"
                  onClick={togglePerDay}
                  className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 rounded-lg border transition ${
                    perDay
                      ? "bg-blue-50 border-blue-200 text-blue-700"
                      : "border-gray-200 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  <SlidersHorizontal className="w-3.5 h-3.5" />
                  {perDay ? "Different times per day" : "Same time every day"}
                </button>
              )}
            </div>

            {!perDay && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="sr-only" htmlFor="day-start">
                    Daily start time
                  </label>
                  <input
                    id="day-start"
                    type="time"
                    className={timeInputClass}
                    value={tripData.daily_start_time}
                    onChange={(event) =>
                      setTripData({ ...tripData, daily_start_time: event.target.value })
                    }
                  />
                </div>
                <div>
                  <label className="sr-only" htmlFor="day-end">
                    Daily end time
                  </label>
                  <input
                    id="day-end"
                    type="time"
                    className={timeInputClass}
                    value={tripData.daily_end_time}
                    onChange={(event) =>
                      setTripData({ ...tripData, daily_end_time: event.target.value })
                    }
                  />
                </div>
              </div>
            )}

            {perDay && (
              <div className="space-y-2">
                {dayRows.map((row, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-3 bg-gray-50 rounded-xl p-2.5"
                  >
                    <div className="w-20 shrink-0">
                      <p className="text-sm font-semibold text-gray-800">Day {index + 1}</p>
                      <p className="text-[10px] text-gray-500">{dateLabel(index)}</p>
                    </div>
                    <input
                      type="time"
                      aria-label={`Day ${index + 1} start`}
                      className="flex-1 min-w-0 px-2.5 py-2 text-sm border border-gray-300 rounded-lg bg-white"
                      value={row.start}
                      onChange={(event) => updateDayRow(index, "start", event.target.value)}
                    />
                    <span className="text-gray-400 text-sm">–</span>
                    <input
                      type="time"
                      aria-label={`Day ${index + 1} end`}
                      className="flex-1 min-w-0 px-2.5 py-2 text-sm border border-gray-300 rounded-lg bg-white"
                      value={row.end}
                      onChange={(event) => updateDayRow(index, "end", event.target.value)}
                    />
                  </div>
                ))}
              </div>
            )}

            <p className="text-[11px] text-gray-500 mt-2">
              {perDay && dayRows.length > 0
                ? `${formatWindowHint(dayRows[0].start, dayRows[0].end)} on Day 1.`
                : `${formatWindowHint(tripData.daily_start_time, tripData.daily_end_time)}.`}
            </p>
          </div>
        </div>
      </div>

      <div className="sticky bottom-3 mt-4 sm:static sm:mt-6">
        <button
          onClick={onNext}
          disabled={!canContinue}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 px-4 rounded-xl transition disabled:opacity-50 shadow-lg sm:shadow-none"
        >
          Next: choose travel vibes
        </button>
      </div>
    </div>
  );
}
