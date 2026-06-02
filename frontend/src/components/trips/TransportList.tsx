// src/components/trips/TransportList.tsx
import { TrainFront } from "lucide-react";
import Card from "@/components/ui/Card";

export default function TransportList() {
  // TODO: Later, this will fetch from GET /api/trips/:id/transport
  return (
    <Card className="p-6">
      <div className="flex items-center gap-3 mb-4">
        <TrainFront size={24} className="text-primary-600" />
        <h3 className="text-xl font-bold text-gray-900">Transport Options</h3>
      </div>
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <div key={i} className="bg-gray-50 rounded-lg p-4 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/4 mb-2"></div>
            <div className="h-3 bg-gray-200 rounded w-1/2"></div>
          </div>
        ))}
      </div>
    </Card>
  );
}