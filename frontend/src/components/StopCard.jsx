import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  ArrowLeftCircle,
  ArrowRightCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  GripVertical,
  Lock,
  MapPin,
  Minus,
  Plus,
  RefreshCw,
  Star,
  Trash2,
} from "lucide-react";
import { format, parseISO } from "date-fns";

const SLOT_LABELS = {
  morning: "Morning",
  midday: "Midday",
  afternoon: "Afternoon",
  evening: "Evening",
  flexible: "Any time",
};

const SLOT_STYLES = {
  morning: "bg-amber-50 text-amber-700",
  midday: "bg-sky-50 text-sky-700",
  afternoon: "bg-indigo-50 text-indigo-700",
  evening: "bg-violet-50 text-violet-700",
  flexible: "bg-gray-50 text-gray-500",
};

function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours && rest) return `${hours}h ${rest}m`;
  if (hours) return `${hours}h`;
  return `${rest}m`;
}

function formatOperatingHours(hours) {
  if (!hours) return null;
  let parsed = hours;
  if (typeof hours === "string") {
    try {
      parsed = JSON.parse(hours);
    } catch {
      return null;
    }
  }
  if (!parsed?.open || !parsed?.close) return null;
  return `${parsed.open}–${parsed.close}`;
}

const ACTION_BUTTON =
  "inline-flex items-center justify-center w-10 h-10 rounded-xl border transition disabled:opacity-30";

export default function StopCard({
  stop,
  index,
  totalDays,
  activeDay,
  onMove,
  onToggleLock,
  onRemove,
  onAdjustDuration,
  onReplace,
  onReorderStep,
  canMoveUp,
  canMoveDown,
  isRecalculating,
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: stop.stop_id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.45 : 1,
  };

  const duration = stop.duration_minutes ?? 90;
  const busy = Boolean(isRecalculating);
  const hours = formatOperatingHours(stop.operating_hours);

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={`bg-white rounded-2xl border shadow-sm overflow-hidden ${
        stop.is_locked ? "border-orange-200 ring-1 ring-orange-100" : "border-gray-100"
      } ${busy ? "pointer-events-none opacity-50" : ""}`}
    >
      {/* Photo banner: drag handle lives here so buttons never fight the gesture. */}
      <div
        {...listeners}
        {...attributes}
        className="relative h-36 sm:h-32 bg-gray-100 touch-none select-none cursor-grab active:cursor-grabbing"
      >
        {stop.photo_url ? (
          <img
            src={stop.photo_url}
            alt={stop.place_name}
            draggable={false}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-300">
            <MapPin className="w-8 h-8" />
          </div>
        )}

        <span className="absolute top-2 left-2 w-8 h-8 rounded-full bg-blue-600 text-white text-sm font-bold flex items-center justify-center shadow">
          {index + 1}
        </span>

        {stop.time_slot && (
          <span
            className={`absolute top-2 right-2 text-[11px] font-semibold px-2 py-1 rounded-full ${
              SLOT_STYLES[stop.time_slot] ?? SLOT_STYLES.flexible
            }`}
          >
            {SLOT_LABELS[stop.time_slot] ?? stop.time_slot}
          </span>
        )}

        <span className="absolute bottom-2 right-2 p-1.5 rounded-lg bg-black/35 text-white">
          <GripVertical className="w-4 h-4" />
        </span>
      </div>

      <div className="p-3.5">
        <h3 className="font-bold text-gray-900 leading-snug break-words">{stop.place_name}</h3>

        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 mt-1 text-[11px] text-gray-500">
          <span className="font-semibold uppercase tracking-wide text-blue-600">
            {stop.primary_category?.replace(/_/g, " ")}
          </span>
          {hours && (
            <span className="inline-flex items-center">
              <Clock className="w-3 h-3 mr-1" />
              {hours}
            </span>
          )}
          {stop.rating > 0 && (
            <span className="inline-flex items-center">
              <Star className="w-3 h-3 mr-0.5 text-yellow-400 fill-current" />
              {stop.rating.toFixed(1)}
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-3">
          <span
            className={`inline-flex items-center text-xs font-bold px-2.5 py-1.5 rounded-lg ${
              stop.is_locked ? "bg-orange-50 text-orange-700" : "bg-gray-100 text-gray-700"
            }`}
          >
            {format(parseISO(stop.scheduled_start), "h:mm a")} –{" "}
            {format(parseISO(stop.scheduled_end), "h:mm a")}
          </span>

          <span className="inline-flex items-center gap-0.5 text-xs text-gray-600 border border-gray-200 rounded-lg">
            <button
              onClick={() => onAdjustDuration(stop.stop_id, duration - 30)}
              disabled={busy || duration <= 15}
              className="w-9 h-9 flex items-center justify-center rounded-l-lg hover:bg-gray-100 disabled:opacity-30"
              aria-label="Shorten this visit by 30 minutes"
            >
              <Minus className="w-4 h-4" />
            </button>
            <span className="font-semibold min-w-[46px] text-center tabular-nums">
              {formatDuration(duration)}
            </span>
            <button
              onClick={() => onAdjustDuration(stop.stop_id, duration + 30)}
              disabled={busy || duration >= 600}
              className="w-9 h-9 flex items-center justify-center rounded-r-lg hover:bg-gray-100 disabled:opacity-30"
              aria-label="Stay 30 minutes longer"
            >
              <Plus className="w-4 h-4" />
            </button>
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 mt-3">
          <button
            onClick={() => onReorderStep(stop.stop_id, -1)}
            disabled={busy || !canMoveUp}
            title="Move earlier in the day"
            className={`${ACTION_BUTTON} border-gray-200 text-gray-500 hover:bg-gray-50`}
          >
            <ChevronUp className="w-4 h-4" />
          </button>
          <button
            onClick={() => onReorderStep(stop.stop_id, 1)}
            disabled={busy || !canMoveDown}
            title="Move later in the day"
            className={`${ACTION_BUTTON} border-gray-200 text-gray-500 hover:bg-gray-50`}
          >
            <ChevronDown className="w-4 h-4" />
          </button>

          {activeDay > 1 && (
            <button
              onClick={() => onMove(stop.stop_id, activeDay - 1)}
              title={`Move to Day ${activeDay - 1}`}
              className={`${ACTION_BUTTON} border-gray-200 text-gray-500 hover:bg-blue-50 hover:text-blue-600`}
            >
              <ArrowLeftCircle className="w-4 h-4" />
            </button>
          )}
          {activeDay < totalDays && (
            <button
              onClick={() => onMove(stop.stop_id, activeDay + 1)}
              title={`Move to Day ${activeDay + 1}`}
              className={`${ACTION_BUTTON} border-gray-200 text-gray-500 hover:bg-blue-50 hover:text-blue-600`}
            >
              <ArrowRightCircle className="w-4 h-4" />
            </button>
          )}

          <span className="flex-1" />

          <button
            onClick={() => onReplace(stop.stop_id)}
            title="Replace with a similar nearby place"
            className={`${ACTION_BUTTON} border-gray-200 text-gray-500 hover:bg-emerald-50 hover:text-emerald-600`}
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => onToggleLock(stop.stop_id, stop.is_locked)}
            title={stop.is_locked ? "Unlock this stop" : "Lock this stop"}
            className={`${ACTION_BUTTON} ${
              stop.is_locked
                ? "border-orange-200 bg-orange-50 text-orange-700"
                : "border-gray-200 text-gray-500 hover:bg-gray-50"
            }`}
          >
            <Lock className="w-4 h-4" />
          </button>
          <button
            onClick={() => onRemove(stop.stop_id)}
            title="Remove this stop"
            className={`${ACTION_BUTTON} border-gray-200 text-gray-500 hover:bg-red-50 hover:text-red-600`}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </article>
  );
}
