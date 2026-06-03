// src/components/trips/WeatherWidget.tsx
"use client";

import { useState, useEffect } from "react";
import { CloudSun, Thermometer, Droplets, Wind } from "lucide-react";
import Card from "@/components/ui/Card";
import { integrationService } from "@/services/integration.service";

// Types extracted EXACTLY from Person 3's weatherService.ts
interface WeatherData {
  current: {
    temperatureC?: number;
    feelsLikeC?: number;
    humidityPercent?: number;
    windSpeedKmh?: number;
    condition?: string;
  };
  forecast: Array<{
    date?: string;
    minTempC?: number;
    maxTempC?: number;
    condition?: string;
  }>;
}

interface WeatherWidgetProps {
  tripId: string;
}

export default function WeatherWidget({ tripId }: WeatherWidgetProps) {
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchWeather() {
      try {
        const data = await integrationService.getWeather(tripId);
        setWeather(data);
      } catch (error) {
        console.error("Weather fetch failed", error);
      } finally {
        setIsLoading(false);
      }
    }

    if (tripId) fetchWeather();
  }, [tripId]);

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <CloudSun size={24} className="text-primary-600" />
          <h3 className="text-xl font-bold text-slate-900">Weather Forecast</h3>
        </div>
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      </Card>
    );
  }

  if (!weather) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <CloudSun size={24} className="text-slate-400" />
          <h3 className="text-xl font-bold text-slate-900">Weather Forecast</h3>
        </div>
        <p className="text-slate-500 text-center py-4">Weather data could not be loaded.</p>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <CloudSun size={24} className="text-primary-600" />
        <h3 className="text-xl font-bold text-slate-900">Weather Forecast</h3>
      </div>

      {/* Current Weather */}
      <div className="bg-primary-50 rounded-xl p-6 mb-6 text-center border border-primary-100">
        <p className="text-slate-600 font-medium mb-1">Right Now</p>
        <p className="text-3xl font-extrabold text-slate-900 mb-1">
          {weather.current.temperatureC ?? '--'}°C
        </p>
        <p className="text-primary-700 font-medium mb-4">{weather.current.condition}</p>
        
        <div className="grid grid-cols-3 gap-4 text-sm border-t border-primary-100 pt-4">
          <div className="flex flex-col items-center">
            <Thermometer size={18} className="text-red-500 mb-1" />
            <span className="text-slate-500">Feels like</span>
            <span className="font-bold text-slate-800">{weather.current.feelsLikeC ?? '--'}°</span>
          </div>
          <div className="flex flex-col items-center">
            <Droplets size={18} className="text-blue-500 mb-1" />
            <span className="text-slate-500">Humidity</span>
            <span className="font-bold text-slate-800">{weather.current.humidityPercent ?? '--'}%</span>
          </div>
          <div className="flex flex-col items-center">
            <Wind size={18} className="text-slate-500 mb-1" />
            <span className="text-slate-500">Wind</span>
            <span className="font-bold text-slate-800">{weather.current.windSpeedKmh ?? '--'} km/h</span>
          </div>
        </div>
      </div>

      {/* 7-Day Forecast List */}
      <h4 className="text-sm font-bold text-slate-700 uppercase tracking-wide mb-3">7-Day Outlook</h4>
      <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
        {weather.forecast.map((day, index) => {
          const dateStr = day.date ? new Date(day.date + "T00:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) : "Unknown date";
          
          return (
            <div key={index} className="flex items-center justify-between bg-slate-50 rounded-lg px-4 py-2 text-sm">
              <span className="text-slate-600 font-medium w-28">{dateStr}</span>
              <span className="text-slate-500 flex-1 text-center">{day.condition}</span>
              <div className="text-slate-800 font-semibold w-24 text-right">
                {day.minTempC ?? '--'}° / {day.maxTempC ?? '--'}°
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}