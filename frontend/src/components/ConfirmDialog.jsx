import { ArrowRight, Loader2, Minus, Plus, TriangleAlert, X } from "lucide-react";

const ACTION_STYLES = {
  move: { icon: ArrowRight, label: "moves", className: "text-blue-600" },
  remove: { icon: Minus, label: "removed", className: "text-red-600" },
  add: { icon: Plus, label: "added", className: "text-emerald-600" },
};

const TITLES = {
  delete: "Remove this stop?",
  replace: "Replace this stop?",
  extend: "Change visit length?",
  move: "Move this stop?",
};

function ChangeRow({ change }) {
  const style = ACTION_STYLES[change.action] ?? ACTION_STYLES.move;
  const Icon = style.icon;

  return (
    <li className="flex items-start gap-2.5 py-2 text-sm">
      <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${style.className}`} />
      <div className="min-w-0 flex-1">
        <span className="font-medium text-gray-900 break-words">{change.place_name}</span>
        <span className="text-gray-500">
          {change.action === "move" && ` moves ${change.from} → ${change.to}`}
          {change.action === "remove" && " is removed"}
          {change.action === "add" && ` is added at ${change.to}`}
        </span>
      </div>
    </li>
  );
}

export default function ConfirmDialog({
  open,
  action,
  preview,
  loading,
  applying,
  error,
  onCancel,
  onApply,
}) {
  if (!open) return null;

  const days = preview?.days ?? [];
  const candidate = preview?.candidate;
  const feasible = preview?.feasible !== false;
  const hasChanges = days.some((day) => day.changes.length > 0 || day.dropped.length > 0);

  return (
    <div className="fixed inset-0 z-[1300] flex items-end justify-center sm:items-center">
      <button
        aria-label="Cancel"
        onClick={onCancel}
        className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm"
      />

      <div className="relative w-full sm:max-w-md max-h-[88vh] overflow-y-auto bg-white rounded-t-3xl sm:rounded-2xl shadow-xl">
        <div className="sticky top-0 bg-white px-5 pt-4 pb-3 border-b border-gray-100 flex items-start justify-between gap-3 rounded-t-3xl sm:rounded-t-2xl">
          <div>
            <h2 className="text-lg font-bold text-gray-900">{TITLES[action] ?? "Apply change?"}</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Nothing is saved until you confirm.
            </p>
          </div>
          <button
            onClick={onCancel}
            aria-label="Close"
            className="p-2 -mr-1 rounded-full text-gray-400 hover:bg-gray-100 hover:text-gray-700"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4">
          {loading && (
            <div className="flex items-center gap-2 text-gray-500 py-8 justify-center text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Working out the consequences…
            </div>
          )}

          {!loading && error && (
            <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl p-3">
              <TriangleAlert className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!loading && !error && (
            <>
              {candidate && (
                <div className="mb-4 rounded-xl border border-emerald-100 bg-emerald-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                    Suggested replacement
                  </p>
                  <p className="font-semibold text-gray-900 mt-1">{candidate.place_name}</p>
                  <p className="text-xs text-gray-600 mt-0.5">
                    {candidate.km_away} km away · {candidate.why}
                  </p>
                </div>
              )}

              {days.map((day) => (
                <div key={day.day_number} className="mb-4 last:mb-0">
                  <p className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-1">
                    Day {day.day_number} · {day.start_time}–{day.end_time}
                  </p>

                  {day.changes.length === 0 && day.dropped.length === 0 ? (
                    <p className="text-sm text-gray-500">Nothing changes on this day.</p>
                  ) : (
                    <ul className="divide-y divide-gray-50 -my-2">
                      {day.changes.map((change, index) => (
                        <ChangeRow key={`${change.place_name}-${index}`} change={change} />
                      ))}
                    </ul>
                  )}

                  {day.dropped.map((item) => (
                    <p key={item.place_name} className="text-xs text-amber-700 mt-1.5">
                      {item.place_name}: {item.reason}
                    </p>
                  ))}

                  {day.relaxed && (
                    <p className="text-xs text-amber-700 mt-1.5">
                      Time-of-day preference would be relaxed to keep the day full.
                    </p>
                  )}

                  {day.overrun_minutes > 0 && (
                    <p className="text-xs text-amber-700 mt-1.5">
                      This day would end {day.overrun_minutes} min past your window.
                    </p>
                  )}
                </div>
              ))}

              {!hasChanges && days.length > 0 && (
                <p className="text-sm text-gray-500">
                  Nothing would move — the result is the same as now.
                </p>
              )}

              {!feasible && (
                <div className="mt-4 flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl p-3">
                  <TriangleAlert className="w-4 h-4 mt-0.5 shrink-0" />
                  <span>This change can't be scheduled within your day window.</span>
                </div>
              )}

              <p className="text-[11px] text-gray-400 mt-4">{preview?.refill_note}</p>
            </>
          )}
        </div>

        <div className="sticky bottom-0 bg-white px-5 py-3 border-t border-gray-100 flex gap-2 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          <button
            onClick={onCancel}
            className="flex-1 py-3 rounded-xl border border-gray-200 font-semibold text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={onApply}
            disabled={loading || applying || Boolean(error) || !feasible}
            className="flex-1 py-3 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 inline-flex items-center justify-center gap-2"
          >
            {applying && <Loader2 className="w-4 h-4 animate-spin" />}
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}
