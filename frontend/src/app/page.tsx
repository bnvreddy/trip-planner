// src/app/page.tsx
import Link from "next/link";
import { Compass, Map, CalendarDays, ArrowRight } from "lucide-react";
import Button from "@/components/ui/Button";

export default function HomePage() {
  return (
    <div className="bg-white">
      {/* Hero Section - Crisp White Background, Dark Text, Green Accents */}
      <section className="relative overflow-hidden bg-white">
        {/* Decorative top bar */}
        <div className="h-2 bg-gradient-to-r from-primary-400 to-primary-600"></div>
        
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 md:py-36 text-center">
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-6 text-slate-900">
            Plan Your Perfect <br />
            <span className="text-primary-600">Journey</span> Today
          </h1>
          
          <p className="max-w-2xl mx-auto text-xl md:text-2xl text-slate-600 mb-12 font-medium">
            Create personalized trips, explore attractions, check transport options, and generate itineraries all in one place.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            {/* Create Trip Button - Solid Bright Emerald */}
            <Link href="/create-trip">
              <Button className="w-full sm:w-auto text-lg px-10 py-4 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all !text-black border-2 border-primary-600 bg-white hover:bg-slate-50">
                Create a Trip <ArrowRight size={20} />
              </Button>
            </Link>
            
            {/* My Trips Button - Clear Emerald Outline */}
            <Link href="/my-trips">
              <Button variant="outline" className="w-full sm:w-auto text-lg px-10 py-4 font-semibold shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all !text-black border-2 border-black hover:bg-slate-100">
                View My Trips
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="bg-slate-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900">Everything You Need</h2>
            <p className="mt-4 text-slate-500 text-lg max-w-xl mx-auto">From weather forecasts to transport bookings, we've got your trip covered.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="bg-white p-8 rounded-2xl text-center hover:shadow-xl transition-all border border-slate-100">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary-100 text-primary-600 mb-6">
                <Compass size={32} />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">Explore Attractions</h3>
              <p className="text-slate-500">Find the best spots at your destination automatically curated just for you.</p>
            </div>

            <div className="bg-white p-8 rounded-2xl text-center hover:shadow-xl transition-all border border-slate-100">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary-100 text-primary-600 mb-6">
                <Map size={32} />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">Smart Transport</h3>
              <p className="text-slate-500">Check buses, trains, and routes seamlessly integrated into your plan.</p>
            </div>

            <div className="bg-white p-8 rounded-2xl text-center hover:shadow-xl transition-all border border-slate-100">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary-100 text-primary-600 mb-6">
                <CalendarDays size={32} />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">Live Weather</h3>
              <p className="text-slate-500">Get real-time weather updates for your travel dates so you pack right.</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}