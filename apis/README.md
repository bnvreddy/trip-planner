# Person 3 - APIs & Integrations

This folder documents the external API choices for the Trip Planner integration work. The executable service code is inside `backend/src/services` so the protected backend routes can import it directly and keep API calls away from the frontend.

## Implemented Integrations

### Weather

- Service file: `backend/src/services/weatherService.ts`
- Backend route: `GET /api/trips/:id/weather`
- Provider: Open-Meteo Forecast API
- Caching: No caching. Weather is volatile and should be fetched live.
- Why this API: Open-Meteo supports coordinate-based forecasts, does not require an API key for non-commercial/student use, and returns forecast data in a simple JSON format.
- Why not alternatives: OpenWeatherMap and WeatherAPI are good options, but their useful plans usually require API key setup and stricter account/rate-limit management for a student merge workflow.
- Official docs: https://open-meteo.com/en/docs

### Attractions

- Service file: `backend/src/services/attractionsService.ts`
- Backend route: `GET /api/trips/:id/attractions`
- Provider: OpenStreetMap data through Overpass API
- Caching: Cached in the trip row as `attractionsData`.
- Why this API: Overpass can query nearby tourism, historic, and park points by latitude/longitude without exposing a paid key.
- Why not alternatives: Google Places and Mapbox Search are stronger commercial products, but they require billing/API-key setup. OpenTripMap is tourism-focused, but also needs an API key.
- Official docs: https://wiki.openstreetmap.org/wiki/Overpass_API

### Transport / Maps Prototype

- Service files: `backend/src/services/transportService.ts` and `backend/src/services/mapsService.ts`
- Backend route: `GET /api/trips/:id/transport`
- Provider: OSRM public route service
- Caching: Cached in the trip row as `transportData`.
- Why this API: OSRM gives road distance, estimated duration, and route geometry using source/destination coordinates. This is useful as a transport prototype without paid setup.
- Why not alternatives: Google Directions, Mapbox Directions, and commercial bus/train providers can provide richer data, but usually need billing, approval, or restricted partner access.
- Feasibility note: Real-time Indian bus/train schedules are not reliably available through a simple free public API. For Week 1, this module provides route estimates and clearly marks that live bus/train schedule data needs a selected provider later.
- Official docs: https://project-osrm.org/docs/

## Normalized Response Goal

The frontend and backend should not handle raw external API responses. Each service returns predictable JSON:

- Weather returns current conditions and a 7-day forecast.
- Attractions returns a clean list with name, category, coordinates, address, and website.
- Transport returns source/destination, road distance, estimated duration, route geometry, and feasibility notes.

## Environment Settings

Optional backend `.env` values:

- `ATTRACTIONS_RADIUS_METERS=5000`
- `ATTRACTIONS_LIMIT=20`

Defaults are already provided in code, so the services can run without these settings.
