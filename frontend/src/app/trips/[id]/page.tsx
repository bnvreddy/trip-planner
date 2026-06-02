// src/app/trips/[id]/page.tsx
import { notFound } from "next/navigation";
import { MapPin, CalendarDays, Wallet, Users, ArrowLeft } from "lucide-react";
import Link from "next/link";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import WeatherWidget from "@/components/trips/WeatherWidget";
import AttractionsList from "@/components/trips/AttractionsList";
import TransportList from "@/components/trips/TransportList";
import { Trip } from "@/types";

// Temporary mock data matching our My Trips page
const mockTrips: Trip[] = [
  { id: "trip-001", source: "New York", destination: "Paris", startDate: "2024-08-15T00:00:00.000Z", endDate: "2024-08-22T00:00:00.000Z", budget: 4000, travelers: 2, destLat: 48.8566, destLng: 2.3522 },
  { id: "trip-002", source: "London", destination: "Tokyo", startDate: "2024-10-01T00:00:00.000Z", endDate: "2024-10-10T00:00:00.000Z", budget: 7500, travelers: 1 },
  { id: "trip-003", source: "San Francisco", destination: "Miami", startDate: "2024-12-20T00:00:00.000Z", endDate: "2024-12-27T00:00:00.000Z", budget: 2500, travelers: 4 }
];

// Added 'async' here
export default async function TripDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  // Added 'await' here!
  const { id } = await params;

  // TODO: Replace this with a real API call: apiFetch(`/trips/${id}`)
  const trip = mockTrips.find((t) => t.id === id);

  if (!trip) {
    notFound(); // Triggers Next.js 404 page if ID doesn't exist
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Back Button */}
      <Link href="/my-trips">
        <Button variant="outline" className="mb-6">
          <ArrowLeft size={18} /> Back to My Trips
        </Button>
      </Link>

      {/* Trip Header */}
      <Card className="p-8 mb-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <MapPin className="text-primary-600" size={32} />
              {trip.destination}
            </h1>
            <p className="text-gray-500 mt-2 flex items-center gap-2">
              <MapPin size={16} /> Trip from <strong className="text-gray-700">{trip.source}</strong>
            </p>
          </div>
          <div className="flex gap-6 text-sm">
            <div className="bg-primary-50 text-primary-700 px-4 py-2 rounded-lg flex items-center gap-2 font-medium">
              <CalendarDays size={16} /> {formatDate(trip.startDate)}
            </div>
            <div className="bg-green-50 text-green-700 px-4 py-2 rounded-lg flex items-center gap-2 font-medium">
              <Wallet size={16} /> ${trip.budget}
            </div>
            <div className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg flex items-center gap-2 font-medium">
              <Users size={16} /> {trip.travelers} People
            </div>
          </div>
        </div>
      </Card>

      {/* Integration Sections Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <WeatherWidget />
        <AttractionsList />
        <div className="lg:col-span-2">
          <TransportList />
        </div>
      </div>
    </div>
  );
}