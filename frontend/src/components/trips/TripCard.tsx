// src/components/trips/TripCard.tsx
import Link from "next/link";
import { MapPin, CalendarDays, Wallet, Users } from "lucide-react";
import { Trip } from "@/types";
import Card from "@/components/ui/Card";

interface TripCardProps {
  trip: Trip;
}

export default function TripCard({ trip }: TripCardProps) {
  // Helper to format dates nicely (e.g., "Aug 15, 2024")
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <Card className="flex flex-col h-full">
      {/* Top colored bar for visual flair */}
      <div className="h-2 bg-gradient-to-r from-primary-500 to-primary-700"></div>
      
      <div className="p-6 flex flex-col flex-grow">
        {/* Destination Header */}
        <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          <MapPin size={20} className="text-primary-600" />
          {trip.destination}
        </h3>

        {/* Trip Details Grid */}
        <div className="grid grid-cols-2 gap-4 text-sm text-gray-600 mb-6 flex-grow">
          <div className="flex items-center gap-2">
            <MapPin size={16} className="text-gray-400" />
            <span>From: <strong className="text-gray-800">{trip.source}</strong></span>
          </div>
          <div className="flex items-center gap-2">
            <Users size={16} className="text-gray-400" />
            <span><strong className="text-gray-800">{trip.travelers}</strong> Travelers</span>
          </div>
          <div className="flex items-center gap-2">
            <CalendarDays size={16} className="text-gray-400" />
            <span>{formatDate(trip.startDate)}</span>
          </div>
          <div className="flex items-center gap-2">
            <Wallet size={16} className="text-gray-400" />
            <span className="text-green-600 font-semibold">${trip.budget}</span>
          </div>
        </div>

        {/* Action Button */}
        <Link href={`/trips/${trip.id}`} className="mt-auto">
          <button className="w-full text-center py-2 px-4 border-2 border-primary-600 text-primary-700 rounded-lg hover:bg-primary-50 transition-colors font-medium">
            View Details
        </button>
        </Link>
      </div>
    </Card>
  );
}