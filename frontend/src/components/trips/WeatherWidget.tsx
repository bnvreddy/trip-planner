// src/components/trips/WeatherWidget.tsx
import { CloudSun } from "lucide-react";
import Card from "@/components/ui/Card";

export default function WeatherWidget() {
  // TODO: Later, this will fetch from GET /api/trips/:id/weather
  return (
    <Card className="p-6">
      <div className="flex items-center gap-3 mb-4">
        <CloudSun size={24} className="text-primary-600" />
        <h3 className="text-xl font-bold text-gray-900">Weather Forecast</h3>
      </div>
      <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500">
        <p className="font-medium">Weather integration loading...</p>
        <p className="text-sm mt-1">(Waiting for Person 3's API)</p>
      </div>
    </Card>
  );
}