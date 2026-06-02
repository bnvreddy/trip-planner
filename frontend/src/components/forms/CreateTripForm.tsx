// src/components/forms/CreateTripForm.tsx
"use client"; // React Hook Form requires client-side rendering

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { createTripSchema, CreateTripFormData } from "@/types";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { CalendarDays, Wallet, Users, MapPin } from "lucide-react";

export default function CreateTripForm() {
  // Initialize React Hook Form with Zod validation
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateTripFormData>({
    resolver: zodResolver(createTripSchema), // Connects our Zod schema to the form
  });

  // This function only runs IF Zod validation passes
  async function onSubmit(data: CreateTripFormData) {
    // TODO: Replace this console.log with the actual API call to Person 2's backend later
    console.log("Trip Data Ready to Send:", data);
    
    // Fake a 1-second network delay so you can see the loading spinner working!
    await new Promise((resolve) => setTimeout(resolve, 1000));
    
    alert("Trip created successfully! (Mock)");
    reset(); // Clears the form fields
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="bg-white p-8 rounded-2xl shadow-lg border border-gray-100 space-y-6">
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Source */}
        <div className="relative">
          <MapPin className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input 
            label="Source City" 
            placeholder="e.g., New York" 
            className="pl-10" 
            {...register("source")} 
            error={errors.source?.message} 
          />
        </div>

        {/* Destination */}
        <div className="relative">
          <MapPin className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input 
            label="Destination City" 
            placeholder="e.g., Paris" 
            className="pl-10" 
            {...register("destination")} 
            error={errors.destination?.message} 
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Start Date */}
        <div className="relative">
          <CalendarDays className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input 
            label="Start Date" 
            type="date" 
            className="pl-10" 
            {...register("startDate")} 
            error={errors.startDate?.message} 
          />
        </div>

        {/* End Date */}
        <div className="relative">
          <CalendarDays className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input 
            label="End Date" 
            type="date" 
            className="pl-10" 
            {...register("endDate")} 
            error={errors.endDate?.message} 
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Budget */}
        <div className="relative">
          <Wallet className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input 
            label="Budget (USD)" 
            type="number" 
            placeholder="5000" 
            className="pl-10" 
            {...register("budget")} 
            error={errors.budget?.message} 
          />
        </div>

        {/* Travelers */}
        <div className="relative">
          <Users className="absolute left-3 top-9 text-gray-400" size={18} />
          <Input 
            label="Number of Travelers" 
            type="number" 
            placeholder="2" 
            className="pl-10" 
            {...register("travelers")} 
            error={errors.travelers?.message} 
          />
        </div>
      </div>

      {/* Submit Button */}
      <div className="pt-4">
        <Button type="submit" isLoading={isSubmitting} className="w-full text-lg py-3">
          Create Trip
        </Button>
      </div>
    </form>
  );
}