// src/app/my-trips/page.tsx
"use client";

import { useState, useEffect } from "react";
import { Briefcase, MapPin } from "lucide-react";
import TripCard from "@/components/trips/TripCard";
import { Trip } from "@/types";
import { tripService } from "@/services/trip.service";
import { useAuth } from "@/context/AuthContext";

export default function MyTripsPage() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const { user } = useAuth();

  // This runs the moment the page loads
  useEffect(() => {
    async function fetchTrips() {
      try {
        const data = await tripService.getMyTrips();
        setTrips(data);
      } catch (error) {
        console.error("Failed to fetch trips", error);
      } finally {
        setIsLoading(false);
      }
    }

    // Only fetch if user is logged in
    if (user) {
      fetchTrips();
    } else {
      setIsLoading(false);
    }
  }, [user]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-12">
      {/* Page Header */}
      <div className="mb-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary-100 text-primary-600 mb-4">
          <Briefcase size={32} />
        </div>
        <h1 className="text-3xl font-bold text-black">My Trips</h1>
        <p className="mt-2 text-slate-600">View and manage all your planned adventures.</p>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="text-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-slate-500">Loading your trips...</p>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && trips.length === 0 && (
        <div className="text-center py-20 bg-white rounded-2xl border border-slate-100 shadow-sm">
          <MapPin size={48} className="mx-auto text-slate-300 mb-4" />
          <p className="text-slate-500 text-lg">You haven&apos;t created any trips yet.</p>
          <p className="text-slate-400 text-sm mt-2">Go to &quot;Create Trip&quot; to start planning!</p>
        </div>
      )}

      {/* Trips Grid (Real Data!) */}
      {!isLoading && trips.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {trips.map((trip) => (
            <TripCard key={trip.id} trip={trip} />
          ))}
        </div>
      )}
    </div>
  );
}