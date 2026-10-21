import {
  DndContext,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Loader2, MapPinOff } from "lucide-react";
import StopCard from "./StopCard";

export default function ItineraryTimeline({
  activeDay,
  totalDays,
  stops,
  onReorder,
  onReorderStep,
  onMove,
  onToggleLock,
  onRemove,
  onAdjustDuration,
  onReplace,
  isRecalculating,
}) {
  // Touch needs a press-and-hold so a scroll gesture is not read as a drag;
  // the mouse gets a small distance threshold instead.
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = stops.findIndex((stop) => stop.stop_id === active.id);
    const newIndex = stops.findIndex((stop) => stop.stop_id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    const reordered = [...stops];
    const [moved] = reordered.splice(oldIndex, 1);
    reordered.splice(newIndex, 0, moved);

    onReorder(activeDay, reordered.map((stop) => stop.stop_id));
  };

  return (
    <div className="relative">
      {isRecalculating && (
        <div className="absolute inset-0 z-50 flex items-start justify-center pt-16 bg-white/60 backdrop-blur-sm rounded-2xl">
          <div className="flex flex-col items-center text-blue-600 bg-white p-5 rounded-2xl shadow-lg border border-blue-100">
            <Loader2 className="w-8 h-8 animate-spin mb-2" />
            <span className="font-bold text-sm">Re-planning the day…</span>
          </div>
        </div>
      )}

      {stops.length === 0 && !isRecalculating && (
        <div className="bg-white border border-dashed border-gray-200 rounded-2xl p-8 text-center">
          <MapPinOff className="w-8 h-8 text-gray-300 mx-auto mb-3" />
          <p className="font-medium text-gray-800">Nothing scheduled on Day {activeDay}</p>
          <p className="text-sm text-gray-500 mt-1">
            Move a stop here from another day, or plan a new trip.
          </p>
        </div>
      )}

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext
          items={stops.map((stop) => stop.stop_id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-3">
            {stops.map((stop, index) => (
              <StopCard
                key={stop.stop_id}
                stop={stop}
                index={index}
                totalDays={totalDays}
                activeDay={activeDay}
                onMove={onMove}
                onToggleLock={onToggleLock}
                onRemove={onRemove}
                onAdjustDuration={onAdjustDuration}
                onReplace={onReplace}
                onReorderStep={onReorderStep}
                canMoveUp={index > 0}
                canMoveDown={index < stops.length - 1}
                isRecalculating={isRecalculating}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}
