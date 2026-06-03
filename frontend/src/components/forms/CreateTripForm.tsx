// src/components/forms/CreateTripForm.tsx
"use client";

import { getCoordinates } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { createTripSchema, CreateTripFormData } from "@/types";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { CalendarDays, Wallet, Users, MapPin } from "lucide-react";
import { tripService } from "@/services/trip.service"; // Import our new service!

export default function CreateTripForm() {
  const router = useRouter(); // Used to redirect after success

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateTripFormData>({
    resolver: zodResolver(createTripSchema),
  });

  async function onSubmit(data: CreateTripFormData) {
    try {
      // 1. Get coordinates for BOTH cities in parallel (faster!)
      const [sourceCoords, destCoords] = await Promise.all([
        getCoordinates(data.source),
        getCoordinates(data.destination),
      ]);

      // 2. Merge the form data with ALL coordinates
      const payload = {
        ...data,
        sourceLat: sourceCoords?.lat ?? null,
        sourceLng: sourceCoords?.lng ?? null,
        destLat: destCoords?.lat ?? null,
        destLng: destCoords?.lng ?? null,
      };

      // 3. Send the enriched payload to Person 2's backend
      await tripService.createTrip(payload);
      
      // 4. Redirect
      window.location.href = "/my-trips"; 
    } catch (error: any) {
      alert(error.message || "Failed to create trip.");
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="bg-white p-8 rounded-2xl shadow-lg border border-slate-100 space-y-6">
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="relative">
          <MapPin className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input label="Source City" placeholder="e.g., New York" className="pl-10" {...register("source")} error={errors.source?.message} />
        </div>
        <div className="relative">
          <MapPin className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input label="Destination City" placeholder="e.g., Paris" className="pl-10" {...register("destination")} error={errors.destination?.message} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="relative">
          <CalendarDays className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input label="Start Date" type="date" className="pl-10" {...register("startDate")} error={errors.startDate?.message} />
        </div>
        <div className="relative">
          <CalendarDays className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input label="End Date" type="date" className="pl-10" {...register("endDate")} error={errors.endDate?.message} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="relative">
          <Wallet className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input label="Budget " type="number" placeholder="5000" className="pl-10" {...register("budget")} error={errors.budget?.message} />
        </div>
        <div className="relative">
          <Users className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input label="Number of Travelers" type="number" placeholder="2" className="pl-10" {...register("travelers")} error={errors.travelers?.message} />
        </div>
      </div>

      <div className="pt-4">
        <Button type="submit" isLoading={isSubmitting} className="w-full text-lg py-3 bg-primary-600 text-white hover:bg-primary-700">
          Create Trip
        </Button>
      </div>
    </form>
  );
}