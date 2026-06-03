// src/lib/api.ts

const API_BASE_URL = "http://localhost:5000/api";

// Helper to safely get the token from local storage (avoids server-side errors)
const getToken = (): string | null => {
  if (typeof window !== "undefined") {
    return localStorage.getItem("token");
  }
  return null;
};

// Our custom fetch wrapper
export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  // If user is logged in, attach the JWT token automatically
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle backend errors (e.g., 401 Unauthorized, 400 Bad Request)
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: "Network error" }));
    throw new Error(errorData.message || "API request failed");
  }

  return response.json();
}