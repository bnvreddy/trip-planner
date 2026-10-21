import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  Map as MapIcon,
  Navigation,
  Plus,
  X,
} from "lucide-react";
import SearchForm from "./components/SearchForm";
import KeywordSelector from "./components/KeywordSelector";
import ItineraryTimeline from "./components/ItineraryTimeline";
import MapView from "./components/MapView";
import MyTrips from "./components/MyTrips";
import ConfirmDialog from "./components/ConfirmDialog";
import AuthView from "./components/AuthView";
import {
  api,
  droppedMessage,
  previewStopChange,
  fetchMe,
  logout as logoutApi,
  getStoredUser,
  getCurrentUserId,
} from "./api";
import { LogOut } from "lucide-react";

const emptyTripData = () => ({
  user_id: getCurrentUserId(),
  destination_city: "",
  start_date: "",
  end_date: "",
  transport_mode: "Driving",
  selected_keywords: [],
  daily_start_time: "09:00",
  daily_end_time: "18:00",
  daily_windows: [],
});

const emptyConfirm = () => ({
  open: false,
  action: null,
  stopId: null,
  targetDay: null,
  durationMinutes: null,
  preview: null,
  loading: false,
  applying: false,
  error: "",
});

export default function App() {
  const [authUser, setAuthUser] = useState(getStoredUser);
  const [view, setView] = useState("wizard"); // "wizard" | "trips"
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [tripData, setTripData] = useState(emptyTripData);
  const [availableKeywords, setAvailableKeywords] = useState({});
  const [itinerary, setItinerary] = useState(null);
  const [activeDay, setActiveDay] = useState(1);
  const [routeState, setRouteState] = useState({ key: null, coordinates: null, source: null });
  const [notice, setNotice] = useState(null);
  const [confirm, setConfirm] = useState(emptyConfirm);
  const [mapOpen, setMapOpen] = useState(false);
  const [suggestionState, setSuggestionState] = useState({ key: null, items: [] });
  const [skippedSuggestions, setSkippedSuggestions] = useState(null);

  // Validate any stored token on load; drop the session if it is stale.
  useEffect(() => {
    fetchMe().then((user) => {
      if (user) setAuthUser(user);
      else setAuthUser(null);
    });
  }, []);

  useEffect(() => {
    if (!authUser) return;
    api
      .get("/keywords")
      .then((res) => setAvailableKeywords(res.data.categories))
      .catch((err) => console.error("Failed to load keywords", err));
  }, [authUser]);

  const handleLogout = () => {
    logoutApi();
    setAuthUser(null);
    setItinerary(null);
    setTripData(emptyTripData());
    setStep(1);
    setView("wizard");
  };

  const showNotice = (text, tone = "info") => setNotice({ text, tone, id: Date.now() });

  useEffect(() => {
    if (!notice) return undefined;
    const timer = setTimeout(() => setNotice(null), 8000);
    return () => clearTimeout(timer);
  }, [notice]);

  const currentDayStops = useMemo(
    () => (itinerary ? itinerary.stops.filter((stop) => stop.day_number === activeDay) : []),
    [itinerary, activeDay],
  );

  const stopSignature = currentDayStops.map((stop) => stop.stop_id).join(",");

  // Keyed by trip + day + stop order: a stale response can never be shown for
  // the day the user is actually looking at.
  const routeKey =
    !itinerary?.trip_id || currentDayStops.length < 2
      ? null
      : `${itinerary.trip_id}:${activeDay}:${stopSignature}`;

  useEffect(() => {
    if (!routeKey) return undefined;
    let alive = true;

    const loadRoute = async () => {
      try {
        const response = await api.get(
          `/trips/${itinerary.trip_id}/days/${activeDay}/route`,
        );
        if (!alive) return;
        const coordinates = response.data.coordinates ?? [];
        setRouteState({
          key: routeKey,
          coordinates: coordinates.length > 1 ? coordinates : null,
          source: response.data.source,
        });
      } catch {
        if (!alive) return;
        setRouteState({ key: routeKey, coordinates: null, source: "unavailable" });
      }
    };

    loadRoute();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeKey]);

  const routeIsCurrent = routeState.key === routeKey;
  const route = routeIsCurrent ? routeState.coordinates : null;
  const routeSource = routeIsCurrent ? routeState.source : null;

  // Places that would fit the visible day. Offered, never inserted.
  const suggestionsKey = itinerary?.trip_id
    ? `${itinerary.trip_id}:${activeDay}:${stopSignature}`
    : null;

  useEffect(() => {
    if (!suggestionsKey) return undefined;
    let alive = true;

    const loadSuggestions = async () => {
      try {
        const response = await api.get(
          `/trips/${itinerary.trip_id}/days/${activeDay}/suggestions`,
        );
        if (alive) {
          setSuggestionState({ key: suggestionsKey, items: response.data.suggestions ?? [] });
        }
      } catch {
        if (alive) setSuggestionState({ key: suggestionsKey, items: [] });
      }
    };

    loadSuggestions();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestionsKey]);

  const suggestions = suggestionState.key === suggestionsKey ? suggestionState.items : [];

  const applyResult = (data, prefix) => {
    if (data?.itinerary) {
      setItinerary(data.itinerary);
      setActiveDay((day) => Math.min(day, data.itinerary.days_count || 1));
    }

    const messages = [];
    let tone = "info";

    if (prefix) messages.push(prefix);

    const dropped = droppedMessage(data?.dropped);
    if (dropped) {
      messages.push(dropped);
      tone = "warn";
    }

    if (data?.added?.length) {
      const names = data.added.map((item) => item.place_name).join(", ");
      messages.push(`Added ${names} to fill the day.`);
    }

    if (data?.relaxed) {
      messages.push("Time-of-day preferences were relaxed to keep this day from emptying.");
    }

    if (data?.overrun_minutes > 0) {
      messages.push(`This order now runs ${data.overrun_minutes} min past your daily window.`);
      tone = "warn";
    }

    if (data?.outside_slot?.length) {
      messages.push(`${data.outside_slot.join(", ")} now sits outside its usual time of day.`);
    }

    if (messages.length) showNotice(messages.join(" "), tone);
  };

  const errorText = (err, fallback) =>
    err?.response?.data?.detail && typeof err.response.data.detail === "string"
      ? err.response.data.detail
      : fallback;

  const handleKeywordToggle = (keyword) => {
    setTripData((prev) => ({
      ...prev,
      selected_keywords: prev.selected_keywords.includes(keyword)
        ? prev.selected_keywords.filter((item) => item !== keyword)
        : [...prev.selected_keywords, keyword],
    }));
  };

  const generateTrip = async () => {
    setLoading(true);
    try {
      const payload = { ...tripData, user_id: getCurrentUserId() };
      if (!payload.daily_windows?.length) delete payload.daily_windows;

      const response = await api.post("/trips/generate", payload);
      setItinerary(response.data.itinerary);
      setActiveDay(1);
      setStep(3);
      setView("wizard");

      const parts = [];
      if (response.data.catalogue_fetched_for?.length) {
        parts.push(
          `Fetched new places for ${response.data.catalogue_fetched_for.join(", ")}.`,
        );
      }
      const dropped = droppedMessage(response.data.dropped);
      if (dropped) parts.push(dropped);
      if (response.data.added?.length) {
        parts.push(`Added ${response.data.added.map((item) => item.place_name).join(", ")}.`);
      }
      if (response.data.relaxed) {
        parts.push("Some days needed their time-of-day preferences relaxed.");
      }
      if (parts.length) showNotice(parts.join(" "), dropped ? "warn" : "info");
    } catch (err) {
      console.error("Error generating trip:", err);
      showNotice(errorText(err, "Failed to generate the trip. Please try again."), "error");
    } finally {
      setLoading(false);
    }
  };

  const withRecalculating = async (task, fallbackMessage) => {
    setIsRecalculating(true);
    try {
      await task();
    } catch (err) {
      console.error(fallbackMessage, err);
      showNotice(errorText(err, fallbackMessage), "error");
    } finally {
      setIsRecalculating(false);
    }
  };

  const toggleLock = async (stopId, currentLockStatus) => {
    setItinerary((prev) => ({
      ...prev,
      stops: prev.stops.map((stop) =>
        stop.stop_id === stopId ? { ...stop, is_locked: !currentLockStatus } : stop,
      ),
    }));

    try {
      await api.post(`/trips/${itinerary.trip_id}/stops/${stopId}/lock`);
    } catch (err) {
      console.error("Lock toggle failed:", err);
      setItinerary((prev) => ({
        ...prev,
        stops: prev.stops.map((stop) =>
          stop.stop_id === stopId ? { ...stop, is_locked: currentLockStatus } : stop,
        ),
      }));
      showNotice("Could not change the lock state.", "error");
    }
  };

  // --------------------------------------------------------------------- //
  // previews
  // --------------------------------------------------------------------- //

  const openPreview = async (action, stopId, extras = {}) => {
    const base = {
      open: true,
      action,
      stopId,
      targetDay: extras.targetDay ?? null,
      durationMinutes: extras.durationMinutes ?? null,
      preview: null,
      loading: true,
      applying: false,
      error: "",
    };
    setConfirm(base);

    const body = { action };
    if (base.targetDay !== null) body.target_day = base.targetDay;
    if (base.durationMinutes !== null) body.duration_minutes = base.durationMinutes;

    try {
      const preview = await previewStopChange(itinerary.trip_id, stopId, body);
      setConfirm((prev) => ({ ...prev, preview, loading: false }));
    } catch (err) {
      setConfirm((prev) => ({
        ...prev,
        loading: false,
        error: errorText(err, "Could not preview that change."),
      }));
    }
  };

  const closePreview = () => setConfirm(emptyConfirm());

  const applyPreview = async () => {
    const { action, stopId, targetDay, durationMinutes, preview } = confirm;
    setConfirm((prev) => ({ ...prev, applying: true, error: "" }));

    try {
      let response;
      if (action === "delete") {
        response = await api.post(
          `/trips/${itinerary.trip_id}/recalculate`,
          null,
          { params: { remove_stop_id: stopId } },
        );
      } else if (action === "replace") {
        response = await api.post(
          `/trips/${itinerary.trip_id}/stops/${stopId}/replace`,
          { place_id: preview?.candidate?.place_id ?? null },
        );
      } else if (action === "extend") {
        response = await api.patch(
          `/trips/${itinerary.trip_id}/stops/${stopId}/duration`,
          { duration_minutes: durationMinutes },
        );
      } else {
        response = await api.post(
          `/trips/${itinerary.trip_id}/stops/${stopId}/move`,
          null,
          { params: { target_day: targetDay } },
        );
      }

      applyResult(
        response.data,
        action === "replace" && response.data.replacement
          ? `Swapped in ${response.data.replacement.place_name}.`
          : undefined,
      );
      closePreview();
    } catch (err) {
      console.error("Apply failed:", err);
      setConfirm((prev) => ({
        ...prev,
        applying: false,
        error: errorText(err, "Could not apply that change."),
      }));
    }
  };

  // --------------------------------------------------------------------- //
  // direct edits (order changes: no confirmation, they are explicit)
  // --------------------------------------------------------------------- //

  const reorderStops = (dayNumber, orderedStopIds) => {
    setItinerary((prev) => {
      const byId = new Map(prev.stops.map((stop) => [stop.stop_id, stop]));
      const reordered = orderedStopIds.map((id) => byId.get(id)).filter(Boolean);
      return {
        ...prev,
        stops: [...prev.stops.filter((stop) => stop.day_number !== dayNumber), ...reordered],
      };
    });

    return withRecalculating(async () => {
      const response = await api.patch(
        `/trips/${itinerary.trip_id}/stops/reorder`,
        { day_number: dayNumber, ordered_stop_ids: orderedStopIds },
      );
      applyResult(response.data);
    }, "Could not save the new order.");
  };

  const reorderStep = (stopId, direction) => {
    const ids = currentDayStops.map((stop) => stop.stop_id);
    const index = ids.indexOf(stopId);
    const target = index + direction;
    if (index === -1 || target < 0 || target >= ids.length) return;

    const next = [...ids];
    [next[index], next[target]] = [next[target], next[index]];
    reorderStops(activeDay, next);
  };

  const addSuggestion = async (place) => {
    setSkippedSuggestions(suggestionsKey);
    await withRecalculating(async () => {
      const response = await api.post(
        `/trips/${itinerary.trip_id}/days/${activeDay}/add`,
        { place_id: place.place_id },
      );
      applyResult(response.data, `Added ${place.place_name}.`);
    }, "Could not add that place.");
  };

  const openTrip = async (tripId) => {
    setLoading(true);
    try {
      const response = await api.get(`/trips/${tripId}/itinerary`);
      setItinerary(response.data);
      setActiveDay(1);
      setStep(3);
      setView("wizard");
    } catch (err) {
      console.error("Failed to open trip", err);
      showNotice(errorText(err, "Could not open that trip."), "error");
    } finally {
      setLoading(false);
    }
  };

  const startNewTrip = () => {
    setItinerary(null);
    setTripData(emptyTripData());
    setStep(1);
    setActiveDay(1);
    setView("wizard");
  };

  if (!authUser) {
    return <AuthView onAuthed={(user) => setAuthUser(user)} />;
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 font-sans">
      <header className="bg-blue-600 text-white shadow-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-3 sm:px-4 h-14 sm:h-16 flex items-center justify-between gap-2">
          <button
            onClick={() => setView("wizard")}
            className="flex items-center gap-2 min-w-0 hover:opacity-90"
          >
            <Navigation className="w-5 h-5 shrink-0" />
            <span className="text-base sm:text-xl font-bold truncate">Andhra AI Planner</span>
          </button>

          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={() => setView("trips")}
              aria-label="My trips"
              className={`inline-flex items-center gap-1.5 text-sm font-semibold px-2.5 sm:px-3 h-9 rounded-lg transition ${
                view === "trips" ? "bg-white/20" : "hover:bg-white/10"
              }`}
            >
              <CalendarDays className="w-4 h-4" />
              <span className="hidden sm:inline">My trips</span>
            </button>
            <button
              onClick={startNewTrip}
              aria-label="New trip"
              className="inline-flex items-center gap-1.5 text-sm font-semibold bg-white text-blue-700 px-2.5 sm:px-3 h-9 rounded-lg hover:bg-blue-50 transition"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">New</span>
            </button>
            <span className="hidden md:inline text-xs text-white/80 max-w-[160px] truncate pl-1">
              {authUser.email}
            </span>
            <button
              onClick={handleLogout}
              aria-label="Sign out"
              title="Sign out"
              className="inline-flex items-center gap-1.5 text-sm font-semibold px-2.5 sm:px-3 h-9 rounded-lg hover:bg-white/10 transition"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      {notice && (
        <div className="fixed inset-x-0 bottom-0 z-[1250] p-3 sm:inset-x-auto sm:bottom-5 sm:right-5 sm:max-w-sm sm:p-0 pointer-events-none">
          <div
            className={`pointer-events-auto flex items-start gap-3 rounded-xl shadow-lg border p-3.5 text-sm bg-white ${
              notice.tone === "error"
                ? "border-red-200 text-red-800"
                : notice.tone === "warn"
                  ? "border-amber-200 text-amber-900"
                  : "border-blue-200 text-blue-900"
            }`}
          >
            {notice.tone !== "info" && <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />}
            <p className="flex-1 break-words">{notice.text}</p>
            <button onClick={() => setNotice(null)} aria-label="Dismiss" className="p-0.5">
              <X className="w-4 h-4 opacity-50 hover:opacity-100" />
            </button>
          </div>
        </div>
      )}

      <main className="max-w-5xl mx-auto px-3 sm:px-4 py-5 sm:py-8">
        {view === "trips" && <MyTrips onOpen={openTrip} onNew={startNewTrip} />}

        {view === "wizard" && step === 1 && (
          <SearchForm tripData={tripData} setTripData={setTripData} onNext={() => setStep(2)} />
        )}

        {view === "wizard" && step === 2 && (
          <KeywordSelector
            tripData={tripData}
            availableKeywords={availableKeywords}
            onToggle={handleKeywordToggle}
            onBack={() => setStep(1)}
            onGenerate={generateTrip}
            loading={loading}
          />
        )}

        {view === "wizard" && step === 3 && itinerary && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
            <div className="lg:col-span-2">
              <div className="mb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="text-2xl sm:text-3xl font-bold truncate">
                      {itinerary.destination}
                    </h2>
                    <p className="text-xs sm:text-sm text-gray-500 mt-1">
                      {itinerary.daily_start_time}–{itinerary.daily_end_time} ·{" "}
                      <span className="capitalize">{itinerary.transport_mode}</span> ·{" "}
                      {itinerary.days_count} days
                    </p>
                  </div>
                  <button
                    onClick={() => setView("trips")}
                    className="text-xs font-semibold text-blue-600 hover:underline shrink-0 mt-1"
                  >
                    All trips
                  </button>
                </div>
              </div>

              <div className="sticky top-14 sm:top-16 z-40 -mx-3 px-3 py-2 mb-3 bg-gray-50/95 backdrop-blur sm:-mx-4 sm:px-4">
                <div className="flex gap-2 overflow-x-auto no-scrollbar">
                  {Array.from({ length: itinerary.days_count }).map((_, index) => (
                    <button
                      key={index}
                      onClick={() => setActiveDay(index + 1)}
                      className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition ${
                        activeDay === index + 1
                          ? "bg-blue-600 text-white shadow"
                          : "bg-white text-gray-600 border border-gray-200"
                      }`}
                    >
                      Day {index + 1}
                    </button>
                  ))}
                </div>
              </div>

              {suggestions.length > 0 && skippedSuggestions !== suggestionsKey && (
                <div className="mb-3 rounded-2xl border border-blue-100 bg-blue-50/60 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[11px] font-bold uppercase tracking-wider text-blue-700">
                      Room left on Day {activeDay}
                    </p>
                    <button
                      onClick={() => setSkippedSuggestions(suggestionsKey)}
                      aria-label="Hide suggestions"
                      className="p-0.5 text-blue-400 hover:text-blue-700"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <ul className="mt-2 space-y-2">
                    {suggestions.map((item) => (
                      <li
                        key={item.place_id}
                        className="flex items-center justify-between gap-2 bg-white rounded-xl px-3 py-2"
                      >
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-gray-900 truncate">
                            {item.place_name}
                          </p>
                          <p className="text-[11px] text-gray-500">
                            {item.slot} · {item.duration_minutes} min · from {item.at}
                          </p>
                        </div>
                        <button
                          onClick={() => addSuggestion(item)}
                          disabled={isRecalculating}
                          className="shrink-0 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-bold hover:bg-blue-700 disabled:opacity-50"
                        >
                          Add
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <ItineraryTimeline
                activeDay={activeDay}
                totalDays={itinerary.days_count}
                stops={currentDayStops}
                onReorder={reorderStops}
                onReorderStep={reorderStep}
                onMove={(stopId, targetDay) => openPreview("move", stopId, { targetDay })}
                onToggleLock={toggleLock}
                onRemove={(stopId) => openPreview("delete", stopId)}
                onAdjustDuration={(stopId, minutes) =>
                  openPreview("extend", stopId, { durationMinutes: minutes })
                }
                onReplace={(stopId) => openPreview("replace", stopId)}
                isRecalculating={isRecalculating || loading}
              />
            </div>

            <div className="hidden lg:block lg:col-span-1">
              <MapView stops={currentDayStops} route={route} routeSource={routeSource} />
            </div>
          </div>
        )}

        {view === "wizard" && step === 3 && !itinerary && !loading && (
          <div className="text-center text-gray-500 py-20">No trip loaded.</div>
        )}
      </main>

      {/* Mobile map sheet */}
      {view === "wizard" && step === 3 && itinerary && (
        <button
          onClick={() => setMapOpen(true)}
          disabled={currentDayStops.length < 2}
          className="lg:hidden fixed bottom-5 right-4 z-[1100] inline-flex items-center gap-2 bg-blue-600 text-white font-semibold px-4 py-3 rounded-full shadow-lg disabled:opacity-50"
        >
          <MapIcon className="w-5 h-5" />
          Route
        </button>
      )}

      {mapOpen && (
        <div className="fixed inset-0 z-[1200] bg-white flex flex-col lg:hidden">
          <div className="flex items-center justify-between px-4 h-14 border-b border-gray-100 shrink-0">
            <h2 className="font-bold">Day {activeDay} route</h2>
            <button
              onClick={() => setMapOpen(false)}
              aria-label="Close map"
              className="p-2 -mr-2 rounded-full text-gray-500 hover:bg-gray-100"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="flex-1 min-h-0 p-2">
            <MapView
              stops={currentDayStops}
              route={route}
              routeSource={routeSource}
              embedded
            />
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirm.open}
        action={confirm.action}
        preview={confirm.preview}
        loading={confirm.loading}
        applying={confirm.applying}
        error={confirm.error}
        onCancel={closePreview}
        onApply={applyPreview}
      />
    </div>
  );
}
