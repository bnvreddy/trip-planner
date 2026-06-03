// src/components/trips/TransportList.tsx
"use client";

import { useState, useEffect } from "react";
import { TrainFront, Route, Clock, Ruler, Info } from "lucide-react";
import Card from "@/components/ui/Card";
import { integrationService } from "@/services/integration.service";

interface TransportOption {
  mode: string;
  label: string;
  available: boolean;
  distanceKm?: number;
  durationMinutes?: number;
  message?: string;
}

interface TransportData {
  route: { from: { name?: string }, to: { name?: string } };
  options: TransportOption[];
  feasibility: { busesAndTrains: string };
}

interface TransportListProps {
  tripId: string;
}

export default function TransportList({ tripId }: TransportListProps) {
  const [data, setData] = useState<TransportData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchTransport() {
      try {
        const res = await integrationService.getTransport(tripId);
        setData(res);
      } catch (error) {
        console.error("Transport fetch failed", error);
      } finally {
        setIsLoading(false);
      }
    }

    if (tripId) fetchTransport();
  }, [tripId]);

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <TrainFront size={24} className="text-primary-600" />
          <h3 className="text-xl font-bold text-slate-900">Transport Options</h3>
        </div>
        <div className="bg-slate-50 rounded-lg p-8 animate-pulse">
          <div className="h-4 bg-slate-200 rounded w-1/4 mb-4 mx-auto"></div>
          <div className="h-3 bg-slate-200 rounded w-1/2 mx-auto"></div>
        </div>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <TrainFront size={24} className="text-slate-400" />
          <h3 className="text-xl font-bold text-slate-900">Transport Options</h3>
        </div>
        <p className="text-slate-500 text-center py-6">Transport data could not be loaded. Ensure source and destination coordinates are saved.</p>
      </Card>
    );
  }

  const roadOption = data.options.find(opt => opt.mode === 'road');

  return (
    <Card className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <TrainFront size={24} className="text-primary-600" />
        <h3 className="text-xl font-bold text-slate-900">Transport Options</h3>
      </div>

      {/* Route Header */}
      <div className="flex items-center justify-center gap-4 mb-8 bg-slate-50 rounded-xl p-4 border border-slate-100">
        <span className="font-bold text-slate-800">{data.route.from.name || "Origin"}</span>
        <Route size={20} className="text-primary-600" />
        <span className="font-bold text-slate-800">{data.route.to.name || "Destination"}</span>
      </div>

      {/* Road Data */}
      {roadOption && roadOption.available ? (
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-blue-50 p-4 rounded-xl text-center border border-blue-100">
            <Ruler size={24} className="mx-auto text-blue-600 mb-2" />
            <p className="text-2xl font-bold text-slate-900">{roadOption.distanceKm}</p>
            <p className="text-sm text-slate-500">Kilometers</p>
          </div>
          <div className="bg-green-50 p-4 rounded-xl text-center border border-green-100">
            <Clock size={24} className="mx-auto text-green-600 mb-2" />
            <p className="text-2xl font-bold text-slate-900">{roadOption.durationMinutes}</p>
            <p className="text-sm text-slate-500">Minutes (Driving)</p>
          </div>
        </div>
      ) : (
        <div className="bg-red-50 p-4 rounded-xl text-center text-red-600 mb-6 border border-red-100">
          {roadOption?.message || "No driving route available."}
        </div>
      )}

      {/* Feasibility Note from Person 3 */}
      <div className="flex gap-3 bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
        <Info size={18} className="flex-shrink-0 mt-0.5" />
        <p className="italic">{data.feasibility.busesAndTrains}</p>
      </div>
    </Card>
  );
}