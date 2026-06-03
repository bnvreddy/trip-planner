// src/lib/utils.ts

// Converts a city name (e.g., "Paris") into Latitude & Longitude
export async function getCoordinates(cityName: string): Promise<{ lat: number; lng: number } | null> {
  try {
    const response = await fetch(
      `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(cityName)}&count=1&language=en&format=json`
    );
    const data = await response.json();

    if (data.results && data.results.length > 0) {
      return {
        lat: data.results[0].latitude,
        lng: data.results[0].longitude,
      };
    }
    return null; // City not found
  } catch (error) {
    console.error("Geocoding failed", error);
    return null;
  }
}