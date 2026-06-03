// src/app/trips/[id]/page.tsx
"use client"; // CRITICAL: Runs in the browser so we can access the JWT token

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { MapPin, CalendarDays, Wallet, Users, ArrowLeft } from "lucide-react";
import Link from "next/link";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import WeatherWidget from "@/components/trips/WeatherWidget";
import AttractionsList from "@/components/trips/AttractionsList";
import TransportList from "@/components/trips/TransportList";
import { Trip } from "@/types";
import { tripService } from "@/services/trip.service";

export default function TripDetailsPage() {
  const params = useParams();
  const id = params.id as string;

  const [trip, setTrip] = useState<Trip | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchTrip() {
      try {
        const data = await tripService.getTripById(id);
        setTrip(data);
      } catch (error) {
        console.error("Failed to fetch trip details", error);
      } finally {
        setIsLoading(false);
      }
    }

    if (id) {
      fetchTrip();
    }
  }, [id]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  };

  // 1. Loading State
  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
        <p className="mt-4 text-slate-500">Loading trip details...</p>
      </div>
    );
  }

  // 2. Error / Not Found State
  if (!trip) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <h2 className="text-2xl font-bold text-slate-900">Trip Not Found</h2>
        <p className="mt-2 text-slate-500">This trip may have been deleted or you don't have access.</p>
        <Link href="/my-trips" className="mt-6 inline-block text-primary-600 font-semibold hover:underline">
          ← Back to My Trips
        </Link>
      </div>
    );
  }

  // 3. Success State (Real Data!)
  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <Link href="/my-trips">
        <Button variant="outline" className="mb-6 border-slate-300 text-slate-700 hover:bg-slate-50">
          <ArrowLeft size={18} /> Back to My Trips
        </Button>
      </Link>

      <Card className="p-8 mb-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div>
            <h1 className="text-3xl font-bold text-black flex items-center gap-3">
              <MapPin className="text-primary-600" size={32} />
              {trip.destination}
            </h1>
            <p className="text-slate-500 mt-2 flex items-center gap-2">
              <MapPin size={16} /> Trip from <strong className="text-slate-800">{trip.source}</strong>
            </p>
          </div>
          <div className="flex flex-wrap gap-4 text-sm">
            <div className="bg-primary-50 text-primary-700 px-4 py-2 rounded-lg flex items-center gap-2 font-medium">
              <CalendarDays size={16} /> {formatDate(trip.startDate)}
            </div>
            <div className="bg-green-50 text-green-700 px-4 py-2 rounded-lg flex items-center gap-2 font-medium">
              <Wallet size={16} /> ${trip.budget}
            </div>
            <div className="bg-slate-100 text-slate-700 px-4 py-2 rounded-lg flex items-center gap-2 font-medium">
              <Users size={16} /> {trip.travelers} People
            </div>
          </div>
        </div>
      </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <WeatherWidget tripId={trip.id} />
        <AttractionsList tripId={trip.id} />
        <div className="lg:col-span-2">
          <TransportList tripId={trip.id} />
        </div>
      </div>
    </div>
  );
}