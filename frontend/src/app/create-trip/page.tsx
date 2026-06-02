// src/app/create-trip/page.tsx
import CreateTripForm from "@/components/forms/CreateTripForm";
import { Plane } from "lucide-react";

export default function CreateTripPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      {/* Page Header */}
      <div className="mb-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary-100 text-primary-600 mb-4">
          <Plane size={32} />
        </div>
        <h1 className="text-3xl font-bold text-gray-900">Create a New Trip</h1>
        <p className="mt-2 text-gray-600">Fill in the details below to start planning your adventure.</p>
      </div>

      {/* The Form */}
      <CreateTripForm />
    </div>
  );
}