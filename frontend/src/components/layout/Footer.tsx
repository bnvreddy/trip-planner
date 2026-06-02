// src/components/layout/Footer.tsx
import { MapPin } from "lucide-react";

export default function Footer() {
  return (
    <footer className="bg-gray-900 text-gray-400 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2 text-white font-bold text-lg">
            <MapPin size={20} className="text-primary-400" />
            TripPlanner
          </div>
          <p className="text-sm">
            © {new Date().getFullYear()} TripPlanner. Built with Next.js & Tailwind.
          </p>
        </div>
      </div>
    </footer>
  );
}