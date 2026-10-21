import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix for default marker icons in Webpack/Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

const DEFAULT_CENTER = [17.6868, 83.2185];

// A numbered pin so the map reads in the same 1-2-3 order as the day list.
// Re-created per order so a reorder/remove/move visibly renumbers the stops.
function numberedIcon(order, isLast) {
  return L.divIcon({
    className: "trip-stop-marker",
    html: `<div style="
        width:30px;height:30px;border-radius:50% 50% 50% 0;
        transform:rotate(-45deg);
        background:${isLast ? "#16a34a" : "#2563eb"};
        border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);
        display:flex;align-items:center;justify-content:center;">
        <span style="transform:rotate(45deg);color:#fff;font-weight:700;font-size:13px;">${order}</span>
      </div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 28],
    popupAnchor: [0, -26],
  });
}

function FitToDay({ points, dayKey }) {
  const map = useMap();

  useEffect(() => {
    if (!points || points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], 14, { animate: true });
      return;
    }
    map.fitBounds(L.latLngBounds(points), { padding: [36, 36], animate: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dayKey, points.length, map]);

  return null;
}

export default function MapView({ stops, route, routeSource, embedded = false }) {
  const orderedStops = useMemo(
    () => stops.filter((stop) => stop.lat && stop.lng),
    [stops],
  );

  const stopPoints = useMemo(
    () => orderedStops.map((stop) => [stop.lat, stop.lng]),
    [orderedStops],
  );

  const center = stopPoints.length > 0 ? stopPoints[0] : DEFAULT_CENTER;
  // Include the order in the key so a reorder (same stops, new sequence) still
  // re-fits the map and re-renders the numbered pins.
  const dayKey = orderedStops.map((stop) => stop.stop_id).join("|");

  // Prefer real road geometry; fall back to connecting the pins.
  const linePoints = route && route.length > 1 ? route : stopPoints;
  const isFallback = !route || route.length < 2;

  return (
    <div
      className={
        embedded
          ? "h-full w-full bg-white rounded-2xl overflow-hidden"
          : "sticky top-24 bg-white rounded-2xl shadow-sm border border-gray-100 p-2"
      }
    >
      <div className={embedded ? "h-full w-full" : "h-[600px] overflow-hidden rounded-2xl relative"}>
        <MapContainer center={center} zoom={12} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution="&copy; OpenStreetMap"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {linePoints.length > 1 && (
            <Polyline
              positions={linePoints}
              pathOptions={{
                color: isFallback ? "#94a3b8" : "#2563eb",
                weight: 4,
                opacity: 0.75,
                dashArray: isFallback ? "6 8" : undefined,
              }}
            />
          )}

          {orderedStops.map((stop, idx) => (
            <Marker
              key={stop.stop_id ?? idx}
              position={[stop.lat, stop.lng]}
              icon={numberedIcon(idx + 1, idx === orderedStops.length - 1)}
            >
              <Popup>
                <b>
                  {idx + 1}. {stop.place_name}
                </b>
                <br />
                {new Date(stop.scheduled_start).toLocaleTimeString([], {
                  hour: "numeric",
                  minute: "2-digit",
                })}
                {" – "}
                {new Date(stop.scheduled_end).toLocaleTimeString([], {
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </Popup>
            </Marker>
          ))}

          <FitToDay points={stopPoints} dayKey={dayKey} />
        </MapContainer>
      </div>

      {!embedded && (
        <p className="px-2 pt-2 pb-1 text-[11px] text-gray-500">
          {routeSource === "osrm" || routeSource === "cache"
            ? "Route geometry from OSRM (free, no live traffic) — displayed times come from Google."
            : "Straight-line preview: road geometry unavailable for this day."}
        </p>
      )}
    </div>
  );
}
