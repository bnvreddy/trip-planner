import { Router } from 'express';
import { createTrip, getTrips, getTripById, updateTrip, deleteTrip } from '../controllers/tripController';
import { getWeather, getAttractions, getTransport } from '../controllers/integrationController'; // <-- Import
import { protect } from '../middleware/authMiddleware';

const router = Router();

// All routes below are protected
router.use(protect);

// Trip CRUD
router.route('/')
  .post(createTrip)
  .get(getTrips);

router.route('/:id')
  .get(getTripById)
  .put(updateTrip)
  .delete(deleteTrip);

// Integration Routes (Person 3)
router.get('/:id/weather', getWeather);
router.get('/:id/attractions', getAttractions);
router.get('/:id/transport', getTransport);

export default router;