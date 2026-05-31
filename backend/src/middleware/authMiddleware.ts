import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';

// Extend Express Request type to include userId
export interface AuthRequest extends Request {
  userId?: string;
}

export const protect = (req: AuthRequest, res: Response, next: NextFunction) => {
  let token;

  // Check for Bearer token in Authorization header
  if (req.headers.authorization && req.headers.authorization.startsWith('Bearer')) {
    try {
      token = req.headers.authorization.split(' ')[1]; // Extract the token
      
      // Verify the token and get the user ID
      const decoded = jwt.verify(token, process.env.JWT_SECRET!) as { id: string };
      
      req.userId = decoded.id; // Attach it to the request object
      next(); // Move to the next middleware/controller
    } catch (error) {
      res.status(401).json({ message: 'Token is not valid' });
    }
  }

  if (!token) {
    res.status(401).json({ message: 'Not authorized, no token' });
  }
};