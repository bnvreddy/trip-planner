import { Response } from 'express';
import prisma from '../prisma';
import { AuthRequest } from '../middleware/authMiddleware';
import * as weatherService from '../services/weatherService';
import * as attractionsService from '../services/attractionsService';
import * as transportService from '../services/transportService';

// GET /api/trips/:id/weather (Live Fetch - No Caching)
export const getWeather = async (req: AuthRequest, res: Response) => {
  const tripId = req.params.id as string;

  try {
    const trip = await prisma.trip.findFirst({ where: { id: tripId, userId: req.userId } });
    if (!trip) return res.status(404).json({ message: 'Trip not found' });

    if (trip.destLat === null || trip.destLng === null) {
      return res.status(400).json({ message: 'Destination coordinates not available for this trip' });
    }

    const weatherData = await weatherService.getWeather(trip.destLat, trip.destLng);

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

    if (trip.destLat === null || trip.destLng === null) {
      return res.status(400).json({ message: 'Destination coordinates not available' });
    }

    // 2. If not cached, fetch from Person 3's service
    const fetchedAttractions = await attractionsService.getAttractions(trip.destLat, trip.destLng);

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

    if (trip.sourceLat === null || trip.sourceLng === null || trip.destLat === null || trip.destLng === null) {
      return res.status(400).json({ message: 'Source/Destination coordinates not available' });
    }

    const fetchedTransport = await transportService.getTransport(
      trip.sourceLat,
      trip.sourceLng,
      trip.destLat,
      trip.destLng,
      trip.source,
      trip.destination
    );

    await prisma.trip.update({
      where: { id: tripId },
      data: { transportData: fetchedTransport }
    });

    res.json(fetchedTransport);
  } catch (error: any) {
    res.status(500).json({ message: 'Server error', error: error.message });
  }
};
