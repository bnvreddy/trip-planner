// src/components/trips/AttractionsList.tsx
"use client";

import { useState, useEffect } from "react";
import { Landmark, MapPin, Globe } from "lucide-react";
import Card from "@/components/ui/Card";
import { integrationService } from "@/services/integration.service";

interface Attraction {
  id: string;
  name: string;
  category: string;
  address: string | null;
  website: string | null;
}

interface AttractionsData {
  count: number;
  attractions: Attraction[];
}

interface AttractionsListProps {
  tripId: string;
}

export default function AttractionsList({ tripId }: AttractionsListProps) {
  const [data, setData] = useState<AttractionsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchAttractions() {
      try {
        const res = await integrationService.getAttractions(tripId);
        setData(res);
      } catch (error) {
        console.error("Attractions fetch failed", error);
      } finally {
        setIsLoading(false);
      }
    }

    if (tripId) fetchAttractions();
  }, [tripId]);

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <Landmark size={24} className="text-primary-600" />
          <h3 className="text-xl font-bold text-slate-900">Nearby Attractions</h3>
        </div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-slate-50 rounded-lg p-4 animate-pulse">
              <div className="h-4 bg-slate-200 rounded w-1/3 mb-2"></div>
              <div className="h-3 bg-slate-200 rounded w-2/3"></div>
            </div>
          ))}
        </div>
      </Card>
    );
  }

  if (!data || data.attractions.length === 0) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <Landmark size={24} className="text-slate-400" />
          <h3 className="text-xl font-bold text-slate-900">Nearby Attractions</h3>
        </div>
        <p className="text-slate-500 text-center py-6">No attractions found for this destination.</p>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Landmark size={24} className="text-primary-600" />
          <h3 className="text-xl font-bold text-slate-900">Nearby Attractions</h3>
        </div>
        <span className="text-xs font-semibold bg-primary-100 text-primary-700 px-2.5 py-1 rounded-full">
          {data.count} found
        </span>
      </div>

      <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
        {data.attractions.map((item) => (
          <div key={item.id} className="border border-slate-100 rounded-lg p-4 hover:shadow-sm transition-shadow bg-white">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <h4 className="font-semibold text-slate-900 mb-1">{item.name}</h4>
                <span className="inline-block text-xs font-medium bg-slate-100 text-slate-600 px-2 py-0.5 rounded mb-2 capitalize">
                  {item.category.replace(/_/g, ' ')}
                </span>
                {item.address && (
                  <p className="text-sm text-slate-500 flex items-center gap-1">
                    <MapPin size={14} className="text-slate-400" /> {item.address}
                  </p>
                )}
              </div>
              {item.website && (
                <a 
                  href={item.website} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-primary-600 hover:text-primary-700 mt-1"
                >
                  <Globe size={20} />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}