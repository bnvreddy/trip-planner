// src/services/integration.service.ts
import { apiFetch } from "@/lib/api";

export const integrationService = {
  getWeather: (tripId: string) =>
    apiFetch<any>(`/trips/${tripId}/weather`),

  getAttractions: (tripId: string) =>
    apiFetch<any>(`/trips/${tripId}/attractions`),

  getTransport: (tripId: string) =>
    apiFetch<any>(`/trips/${tripId}/transport`),
};