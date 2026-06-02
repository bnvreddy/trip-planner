// src/app/my-trips/page.tsx
import { Briefcase } from "lucide-react";
import TripCard from "@/components/trips/TripCard";
import { Trip } from "@/types";

// --- MOCK DATA (Matches Person 2's exact schema) ---
// We will delete this array later and replace it with a fetch() call
const mockTrips: Trip[] = [
  {
    id: "trip-001",
    source: "New York",
    destination: "Paris",
    startDate: "2024-08-15T00:00:00.000Z",
    endDate: "2024-08-22T00:00:00.000Z",
    budget: 4000,
    travelers: 2,
    sourceLat: 40.7128,
    sourceLng: -74.006,
    destLat: 48.8566,
    destLng: 2.3522,
  },
  {
    id: "trip-002",
    source: "London",
    destination: "Tokyo",
    startDate: "2024-10-01T00:00:00.000Z",
    endDate: "2024-10-10T00:00:00.000Z",
    budget: 7500,
    travelers: 1,
    sourceLat: 51.5074,
    sourceLng: -0.1278,
    destLat: 35.6762,
    destLng: 139.6503,
  },
  {
    id: "trip-003",
    source: "San Francisco",
    destination: "Miami",
    startDate: "2024-12-20T00:00:00.000Z",
    endDate: "2024-12-27T00:00:00.000Z",
    budget: 2500,
    travelers: 4,
  }
];
// -----------------------------------------------

export default function MyTripsPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 py-12">
      {/* Page Header */}
      <div className="mb-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary-100 text-primary-600 mb-4">
          <Briefcase size={32} />
        </div>
        <h1 className="text-3xl font-bold text-gray-900">My Trips</h1>
        <p className="mt-2 text-gray-600">View and manage all your planned adventures.</p>
      </div>

      {/* Trips Grid */}
      {mockTrips.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {mockTrips.map((trip) => (
            <TripCard key={trip.id} trip={trip} />
          ))}
        </div>
      ) : (
        <div className="text-center py-20 bg-white rounded-2xl border border-gray-100">
          <p className="text-gray-500 text-lg">You haven&apos;t created any trips yet.</p>
        </div>
      )}
    </div>
  );
}