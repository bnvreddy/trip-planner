import { fetchJson } from './httpClient';

type OverpassElement = {
  id: number;
  type: string;
  lat?: number;
  lon?: number;
  center?: {
    lat?: number;
    lon?: number;
  };
  tags?: Record<string, string>;
};

type OverpassResponse = {
  elements?: OverpassElement[];
};

const getCategory = (tags: Record<string, string> = {}) => {
  if (tags.tourism) return tags.tourism;
  if (tags.historic) return `historic_${tags.historic}`;
  if (tags.leisure) return tags.leisure;
  if (tags.amenity) return tags.amenity;
  return 'attraction';
};

export const getAttractions = async (latitude: number, longitude: number) => {
  const radiusMeters = Number(process.env.ATTRACTIONS_RADIUS_METERS || 5000);
  const limit = Number(process.env.ATTRACTIONS_LIMIT || 20);

  const query = `
    [out:json][timeout:25];
    (
      node(around:${radiusMeters},${latitude},${longitude})["tourism"];
      way(around:${radiusMeters},${latitude},${longitude})["tourism"];
      relation(around:${radiusMeters},${latitude},${longitude})["tourism"];
      node(around:${radiusMeters},${latitude},${longitude})["historic"];
      way(around:${radiusMeters},${latitude},${longitude})["historic"];
      node(around:${radiusMeters},${latitude},${longitude})["leisure"="park"];
      way(around:${radiusMeters},${latitude},${longitude})["leisure"="park"];
    );
    out center tags ${limit};
  `;

  const body = new URLSearchParams({ data: query });
  const data = await fetchJson<OverpassResponse>('Overpass API', 'https://overpass-api.de/api/interpreter', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
    body,
  }, 25000);

  const attractions = (data.elements || [])
    .map((element) => {
      const tags = element.tags || {};
      const lat = element.lat ?? element.center?.lat;
      const lng = element.lon ?? element.center?.lon;

      return {
        id: `${element.type}-${element.id}`,
        name: tags.name || tags['name:en'] || 'Unnamed attraction',
        category: getCategory(tags),
        coordinates: lat !== undefined && lng !== undefined ? { lat, lng } : null,
        address: tags['addr:full'] || tags['addr:street'] || tags['addr:city'] || null,
        website: tags.website || tags.url || null,
        source: 'OpenStreetMap',
      };
    })
    .filter((item) => item.name !== 'Unnamed attraction' && item.coordinates)
    .slice(0, limit);

  return {
    provider: 'OpenStreetMap Overpass API',
    coordinatesUsed: { lat: latitude, lng: longitude },
    radiusMeters,
    count: attractions.length,
    attractions,
  };
};
