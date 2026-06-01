import { getRoadRoute } from './mapsService';

export const getTransport = async (
  sourceLat: number,
  sourceLng: number,
  destLat: number,
  destLng: number,
  source?: string,
  destination?: string
) => {
  const roadRoute = await getRoadRoute(sourceLat, sourceLng, destLat, destLng);

  return {
    provider: 'OSRM public route service',
    route: {
      from: { name: source, lat: sourceLat, lng: sourceLng },
      to: { name: destination, lat: destLat, lng: destLng },
    },
    options: [
      {
        mode: 'road',
        label: 'Road route estimate',
        ...roadRoute,
      },
    ],
    feasibility: {
      busesAndTrains: 'Real-time bus/train schedules usually require paid or restricted provider APIs. This service returns a route estimate now and can be extended when the team selects a transport data provider.',
      cacheRecommended: true,
    },
  };
};
