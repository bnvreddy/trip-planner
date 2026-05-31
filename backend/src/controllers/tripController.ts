import { Response } from 'express';
import prisma from '../prisma';
import { AuthRequest } from '../middleware/authMiddleware';

// POST /api/trips
export const createTrip = async (req: AuthRequest, res: Response) => {
  const { source, destination, startDate, endDate, budget, travelers, sourceLat, sourceLng, destLat, destLng } = req.body;
  const userId = req.userId!;

  try {
    if (!source || !destination || !startDate || !endDate || !budget || !travelers) {
      return res.status(400).json({ message: 'Please fill all required fields' });
    }

    const trip = await prisma.trip.create({
      data: {
        source,
        destination,
        startDate: new Date(startDate),
        endDate: new Date(endDate),
        budget: parseFloat(budget),
        travelers: parseInt(travelers),
        sourceLat: sourceLat ? parseFloat(sourceLat) : null,
        sourceLng: sourceLng ? parseFloat(sourceLng) : null,
        destLat: destLat ? parseFloat(destLat) : null,
        destLng: destLng ? parseFloat(destLng) : null,
        userId,
      },
    });
    res.status(201).json(trip);
  } catch (error: any) {
    res.status(500).json({ message: 'Server error', error: error.message });
  }
};

// GET /api/trips
export const getTrips = async (req: AuthRequest, res: Response) => {
  try {
    const trips = await prisma.trip.findMany({
      where: { userId: req.userId },
      orderBy: { createdAt: 'desc' },
    });
    res.json(trips);
  } catch (error: any) {
    res.status(500).json({ message: 'Server error', error: error.message });
  }
};

// GET /api/trips/:id
export const getTripById = async (req: AuthRequest, res: Response) => {
  // FIX: Tell TypeScript this is definitely a string
  const tripId = req.params.id as string; 
  
  try {
    const trip = await prisma.trip.findFirst({
      where: { id: tripId, userId: req.userId },
    });
    if (!trip) return res.status(404).json({ message: 'Trip not found' });
    res.json(trip);
  } catch (error: any) {
    res.status(500).json({ message: 'Server error', error: error.message });
  }
};

// PUT /api/trips/:id
export const updateTrip = async (req: AuthRequest, res: Response) => {
  // FIX: Tell TypeScript this is definitely a string
  const tripId = req.params.id as string;

  try {
    let trip = await prisma.trip.findFirst({ where: { id: tripId, userId: req.userId } });
    if (!trip) return res.status(404).json({ message: 'Trip not found' });

    const updatedTrip = await prisma.trip.update({
      where: { id: tripId },
      data: req.body, // Person 3 can send attractionsData/transportData here later
    });
    res.json(updatedTrip);
  } catch (error: any) {
    res.status(500).json({ message: 'Server error', error: error.message });
  }
};

// DELETE /api/trips/:id
export const deleteTrip = async (req: AuthRequest, res: Response) => {
  // FIX: Tell TypeScript this is definitely a string
  const tripId = req.params.id as string;

  try {
    let trip = await prisma.trip.findFirst({ where: { id: tripId, userId: req.userId } });
    if (!trip) return res.status(404).json({ message: 'Trip not found' });

    await prisma.trip.delete({ where: { id: tripId } });
    res.json({ message: 'Trip deleted successfully' });
  } catch (error: any) {
    res.status(500).json({ message: 'Server error', error: error.message });
  }
};