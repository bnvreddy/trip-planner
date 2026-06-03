// src/components/layout/Navbar.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Menu, X, MapPin, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext"; // Import Auth hook

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const { user, logout } = useAuth(); // Get user state and logout function
  const router = useRouter();

  const navLinks = [
    { href: "/", label: "Home" },
    { href: "/create-trip", label: "Create Trip" },
    { href: "/my-trips", label: "My Trips" },
  ];

  const handleLogout = () => {
    logout();
    router.push("/"); // Send user back to home page after logout
  };

  return (
    <nav className="bg-white shadow-sm border-b border-gray-100 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 text-black font-bold text-xl">
            <MapPin size={24} className="text-black" />
            <span>TripPlanner</span>
          </Link>

          {/* Desktop Links */}
          <div className="hidden md:flex items-center gap-6">
            {navLinks.map((link) => (
              <Link 
                key={link.href} 
                href={link.href} 
                className="text-slate-600 hover:text-primary-600 transition-colors font-medium"
              >
                {link.label}
              </Link>
            ))}
            
            {/* Dynamic Auth Section */}
            {user ? (
              <div className="flex items-center gap-4">
                <span className="text-sm text-slate-600 font-medium border border-slate-200 px-3 py-1 rounded-full">
                  {user.email}
                </span>
                <button 
                  onClick={handleLogout} 
                  className="flex items-center gap-2 text-red-600 hover:text-red-700 font-medium transition-colors"
                >
                  <LogOut size={18} />
                  Logout
                </button>
              </div>
            ) : (
              <Link href="/login" className="bg-accent-500 text-black px-4 py-2 rounded-lg hover:bg-accent-600 transition-colors">
                Login
              </Link>
            )}
          </div>

          {/* Mobile Menu Button */}
          <button 
            onClick={() => setIsOpen(!isOpen)} 
            className="md:hidden text-slate-600"
          >
            {isOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
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
          
          {/* Mobile Dynamic Auth Section */}
          {user ? (
            <div className="mt-4 flex flex-col gap-3">
              <span className="text-sm text-slate-600 font-medium text-center">{user.email}</span>
              <button 
                onClick={() => { handleLogout(); setIsOpen(false); }} 
                className="flex items-center justify-center gap-2 text-red-600 hover:text-red-700 font-medium py-2"
              >
                <LogOut size={18} />
                Logout
              </button>
            </div>
          ) : (
            <Link 
              href="/login" 
              onClick={() => setIsOpen(false)}
              className="block mt-3 text-center bg-accent-500 text-black px-4 py-2 rounded-lg hover:bg-accent-600"
            >
              Login
            </Link>
          )}
        </div>
      )}
    </nav>
  );
}