// src/components/layout/Navbar.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X, MapPin } from "lucide-react";

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);

  const navLinks = [
    { href: "/", label: "Home" },
    { href: "/create-trip", label: "Create Trip" },
    { href: "/my-trips", label: "My Trips" },
  ];

  return (
    <nav className="bg-white shadow-sm border-b border-gray-100 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          
          <Link href="/" className="flex items-center gap-2 text-primary-600 font-bold text-xl">
            <MapPin size={24} />
            <span>TripPlanner</span>
          </Link>

          <div className="hidden md:flex items-center gap-6">
            {navLinks.map((link) => (
              <Link 
                key={link.href} 
                href={link.href} 
                className="text-slate-600 hover:text-primary-600 transition-colors font-medium" // Changed text color to slate
              >
                {link.label}
              </Link>
            ))}
            <Link href="/login" className="bg-accent-500 text-white px-4 py-2 rounded-lg hover:bg-accent-600 transition-colors">
              Login
            </Link>
          </div>

          <button 
            onClick={() => setIsOpen(!isOpen)} 
            className="md:hidden text-slate-600" // Changed text color to slate
          >
            {isOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {isOpen && (
        <div className="md:hidden bg-white border-t border-gray-100 px-4 pb-4">
          {navLinks.map((link) => (
            <Link 
              key={link.href} 
              href={link.href} 
              onClick={() => setIsOpen(false)}
              className="block py-3 text-slate-600 hover:text-primary-600 font-medium border-b border-gray-50"
            >
              {link.label}
            </Link>
          ))}
          <Link 
            href="/login" 
            onClick={() => setIsOpen(false)}
            className="block mt-3 text-center bg-accent-500 text-white px-4 py-2 rounded-lg hover:bg-accent-600"
          >
            Login
          </Link>
        </div>
      )}
    </nav>
  );
}