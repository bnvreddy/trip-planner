// src/types/index.ts
import { z } from "zod";

// ==========================================
// 1. AUTHENTICATION TYPES (Person 2's Auth Routes)
// ==========================================

export interface User {
  id: string;
  email: string;
}

export interface AuthResponse extends User {
  token: string; // JWT token we will save locally
}

// ==========================================
// 2. TRIP TYPES (Person 2's Trip Routes)
// ==========================================

export interface Trip {
  id: string;
  source: string;
  destination: string;
  startDate: string; // Sent as ISO string from backend
  endDate: string;   // Sent as ISO string from backend
  budget: number;
  travelers: number;
  
  // Coordinates (Optional for Week 1, as per Person 2's note)
  sourceLat?: number | null;
  sourceLng?: number | null;
  destLat?: number | null;
  destLng?: number | null;
  
  // Integration Data (JSON, shape depends on Person 3)
  attractionsData?: any; 
  transportData?: any;
}

// ==========================================
// 3. ZOD VALIDATION SCHEMA (For React Hook Form)
// ==========================================
// We define the schema here so the form knows exactly what to validate.
// We use .refine to ensure endDate is after startDate.

export const createTripSchema = z.object({
  source: z.string().min(1, "Source is required"),
  destination: z.string().min(1, "Destination is required"),
  startDate: z.string().min(1, "Start date is required"),
  endDate: z.string().min(1, "End date is required"),
  budget: z.coerce.number().min(1, "Budget must be greater than 0"),
  travelers: z.coerce.number().min(1, "At least 1 traveler is required"),
}).refine((data) => new Date(data.endDate) >= new Date(data.startDate), {
  message: "End date cannot be before start date",
  path: ["endDate"], // Error will attach to the endDate field
});

// Infer the TypeScript type FROM the Zod schema. 
// This guarantees our form data type perfectly matches our validation rules.
export type CreateTripFormData = z.infer<typeof createTripSchema>;