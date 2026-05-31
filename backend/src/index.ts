import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import authRoutes from './routes/authRoutes'; // Import the auth routes
import tripRoutes from './routes/tripRoutes'; // Import the trip routes
dotenv.config();

const app = express();

// Middleware
app.use(cors());
app.use(express.json()); // Allows us to parse JSON in req.body

// API Routes
app.use('/api/auth', authRoutes); 
app.use('/api/trips', tripRoutes); // Any request to /api/trips will go to tripRoutes

// Basic Health Check Route
app.get('/api/health', (req, res) => {
  res.json({ status: 'Backend is up and running!' });
});

// Global Error Handler
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error(err.stack);
  res.status(500).json({ message: 'Something went wrong!' });
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`🚀 Server is running on http://localhost:${PORT}`);
});