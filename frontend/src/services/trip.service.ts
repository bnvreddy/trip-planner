// src/services/trip.service.ts
import { apiFetch } from "@/lib/api";
import { Trip, CreateTripFormData } from "@/types";

export const tripService = {
  // POST /api/trips
  createTrip: (data: CreateTripFormData) =>
    apiFetch<Trip>("/trips", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // GET /api/trips
  getMyTrips: () =>
    apiFetch<Trip[]>("/trips", {
      method: "GET",
    }),

  // GET /api/trips/:id
  getTripById: (id: string) =>
    apiFetch<Trip>(`/trips/${id}`, {
      method: "GET",
    }),

  // DELETE /api/trips/:id
  deleteTrip: (id: string) =>
    apiFetch<{ message: string }>(`/trips/${id}`, {
      method: "DELETE",
    }),
};