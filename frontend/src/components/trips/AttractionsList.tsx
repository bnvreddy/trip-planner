// src/components/trips/AttractionsList.tsx
import { Landmark } from "lucide-react";
import Card from "@/components/ui/Card";

export default function AttractionsList() {
  // TODO: Later, this will fetch from GET /api/trips/:id/attractions
  return (
    <Card className="p-6">
      <div className="flex items-center gap-3 mb-4">
        <Landmark size={24} className="text-primary-600" />
        <h3 className="text-xl font-bold text-gray-900">Nearby Attractions</h3>
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-gray-50 rounded-lg p-4 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/3 mb-2"></div>
            <div className="h-3 bg-gray-200 rounded w-2/3"></div>
          </div>
        ))}
      </div>
    </Card>
  );
}