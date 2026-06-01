import { fetchJson } from './httpClient';

type OsrmRoute = {
  distance: number;
  duration: number;
  geometry?: string;
};

type OsrmResponse = {
  code: string;
  routes?: OsrmRoute[];
};

export const getRoadRoute = async (
  sourceLat: number,
  sourceLng: number,
  destLat: number,
  destLng: number
) => {
  const coordinates = `${sourceLng},${sourceLat};${destLng},${destLat}`;
  const params = new URLSearchParams({
    overview: 'simplified',
    geometries: 'geojson',
    alternatives: 'false',
    steps: 'false',
  });

  const data = await fetchJson<OsrmResponse>(
    'OSRM',
    `https://router.project-osrm.org/route/v1/driving/${coordinates}?${params.toString()}`
  );

  const route = data.routes?.[0];
  if (!route) {
    return {
      provider: 'OSRM',
      available: false,
      message: 'No road route found for these coordinates',
    };
  }

  return {
    provider: 'OSRM',
    available: true,
    distanceKm: Number((route.distance / 1000).toFixed(2)),
    durationMinutes: Math.round(route.duration / 60),
    geometry: route.geometry || null,
  };
};
