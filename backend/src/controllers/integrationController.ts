import { Response } from 'express';
import prisma from '../prisma';
import { AuthRequest } from '../middleware/authMiddleware';

// GET /api/trips/:id/weather (Live Fetch - No Caching)
export const getWeather = async (req: AuthRequest, res: Response) => {
  const tripId = req.params.id as string;

  try {
    const trip = await prisma.trip.findFirst({ where: { id: tripId, userId: req.userId } });
    if (!trip) return res.status(404).json({ message: 'Trip not found' });

    if (!trip.destLat || !trip.destLng) {
      return res.status(400).json({ message: 'Destination coordinates not available for this trip' });
    }

    // TODO: Person 3 will import their weather service here
    // const weatherData = await weatherService.getWeather(trip.destLat, trip.destLng);
    const weatherData = { 
      message: "Weather service not yet integrated by Person 3", 
      coordinatesUsed: { lat: trip.destLat, lng: trip.destLng } 
    };

    res.json(weatherData);
  } catch (error: any) {
    res.status(500).json({ message: 'Server error', error: error.message });
  }
};

// GET /api/trips/:id/attractions (Cache Strategy)
export const getAttractions = async (req: AuthRequest, res: Response) => {
  const tripId = req.params.id as string;

  try {
    const trip = await prisma.trip.findFirst({ where: { id: tripId, userId: req.userId } });
    if (!trip) return res.status(404).json({ message: 'Trip not found' });

    // 1. Check if data is already cached in DB
    if (trip.attractionsData) {
      return res.json(trip.attractionsData);
    }

    if (!trip.destLat || !trip.destLng) {
      return res.status(400).json({ message: 'Destination coordinates not available' });
    }

    // 2. If not cached, fetch from Person 3's service
    // TODO: Person 3 will import their attractions service here
    // const fetchedAttractions = await attractionsService.getAttractions(trip.destLat, trip.destLng);
    const fetchedAttractions = { 
      message: "Attractions service not yet integrated by Person 3",
      coordinatesUsed: { lat: trip.destLat, lng: trip.destLng }
    };

    // 3. Save to DB for future caching
    await prisma.trip.update({
      where: { id: tripId },
      data: { attractionsData: fetchedAttractions }
    });

    res.json(fetchedAttractions);
  } catch (error: any) {
    res.status(500).json({ message: 'Server error', error: error.message });
  }
};

// GET /api/trips/:id/transport (Cache Strategy)
export const getTransport = async (req: AuthRequest, res: Response) => {
  const tripId = req.params.id as string;

  try {
    const trip = await prisma.trip.findFirst({ where: { id: tripId, userId: req.userId } });
    if (!trip) return res.status(404).json({ message: 'Trip not found' });

    if (trip.transportData) {
      return res.json(trip.transportData);
    }

    if (!trip.sourceLat || !trip.sourceLng || !trip.destLat || !trip.destLng) {
      return res.status(400).json({ message: 'Source/Destination coordinates not available' });
    }

    // TODO: Person 3 will import their transport service here
    const fetchedTransport = { 
      message: "Transport service not yet integrated by Person 3",
      route: { from: { lat: trip.sourceLat, lng: trip.sourceLng }, to: { lat: trip.destLat, lng: trip.destLng } }
    };

    await prisma.trip.update({
      where: { id: tripId },
      data: { transportData: fetchedTransport }
    });

    res.json(fetchedTransport);
  } catch (error: any) {
    res.status(500).json({ message: 'Server error', error: error.message });
  }
};