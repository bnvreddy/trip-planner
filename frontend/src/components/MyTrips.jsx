import { useEffect, useState } from "react";
import { Calendar, Loader2, MapPin, Plus, Trash2 } from "lucide-react";
import { api, deleteTrip, getCurrentUserId } from "../api";

function formatRange(start, end) {
  const parse = (value) => (value ? new Date(value) : null);
  const s = parse(start);
  const e = parse(end);
  if (!s || !e) return "Dates not set";
  const opts = { month: "short", day: "numeric" };
  return `${s.toLocaleDateString(undefined, opts)} – ${e.toLocaleDateString(undefined, opts)}`;
}

export default function MyTrips({ onOpen, onNew }) {
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  const loadTrips = () => {
    setLoading(true);
    api
      .get("/trips", { params: { user_id: getCurrentUserId() } })
      .then((res) => setTrips(res.data.trips ?? []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTrips();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDelete = async (tripId) => {
    if (!window.confirm("Delete this trip? This cannot be undone.")) return;
    setDeletingId(tripId);
    try {
      await deleteTrip(tripId);
      setTrips((prev) => prev.filter((trip) => trip.trip_id !== tripId));
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Could not delete the trip.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-3xl font-bold">My trips</h2>
          <p className="text-gray-500 mt-1">Reopen a plan and keep editing it.</p>
        </div>
        <button
          onClick={onNew}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2.5 rounded-xl transition"
        >
          <Plus className="w-4 h-4" />
          New trip
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-gray-500 py-16 justify-center">
          <Loader2 className="w-5 h-5 animate-spin" />
          Loading your trips…
        </div>
      )}

      {error && !loading && (
        <div className="bg-red-50 border border-red-100 text-red-700 rounded-2xl p-4 text-sm mb-3">
          {error}
        </div>
      )}

      {!loading && !error && trips.length === 0 && (
        <div className="bg-white border border-gray-100 rounded-2xl p-10 text-center">
          <MapPin className="w-8 h-8 text-gray-300 mx-auto mb-3" />
          <p className="font-medium text-gray-800">No saved trips yet</p>
          <p className="text-sm text-gray-500 mt-1">Generate one and it will show up here.</p>
        </div>
      )}

      <div className="space-y-3">
        {trips.map((trip) => (
          <div
            key={trip.trip_id}
            className="bg-white border border-gray-100 hover:border-blue-200 hover:shadow-md rounded-2xl p-5 transition flex items-center justify-between gap-4"
          >
            <button
              onClick={() => onOpen(trip.trip_id)}
              className="flex-1 text-left min-w-0"
            >
              <p className="text-lg font-bold text-gray-900 truncate">{trip.city}</p>
              <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-gray-500">
                <span className="inline-flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5" />
                  {formatRange(trip.start_date, trip.end_date)}
                </span>
                <span>{trip.days_count} days</span>
                <span>{trip.stop_count} stops</span>
                <span className="capitalize">{trip.transport_mode}</span>
              </div>
            </button>

            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => onOpen(trip.trip_id)}
                className="text-sm font-semibold text-blue-600 hover:underline"
              >
                Open
              </button>
              <button
                onClick={() => handleDelete(trip.trip_id)}
                disabled={deletingId === trip.trip_id}
                aria-label="Delete trip"
                title="Delete trip"
                className="inline-flex items-center justify-center w-9 h-9 rounded-xl border border-gray-200 text-gray-400 hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition disabled:opacity-50"
              >
                {deletingId === trip.trip_id ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
