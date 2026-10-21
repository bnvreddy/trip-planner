import json
import requests
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.config import settings

def parse_time_window(hours_input) -> tuple:
    start_min = 540
    end_min = 1080
    try:
        if hours_input:
            if isinstance(hours_input, str):
                hours = json.loads(hours_input)
            elif isinstance(hours_input, dict):
                hours = hours_input
            else:
                hours = {}

            open_str = hours.get("open", "09:00")
            close_str = hours.get("close", "18:00")
            o_h, o_m = map(int, open_str.split(":"))
            c_h, c_m = map(int, close_str.split(":"))
            start_min = (o_h * 60) + o_m
            end_min = (c_h * 60) + c_m
    except Exception as e:
        print(f"Time window parsing error: {e}")
    return (start_min, end_min)

def estimate_visit_duration(place_types: list) -> int:
    if not place_types:
        return 90
    types_str = " ".join(place_types).lower()
    if any(t in types_str for t in ["amusement_park", "zoo", "aquarium", "national_park"]): return 180
    if any(t in types_str for t in ["museum", "historical_landmark", "art_gallery"]): return 120
    if any(t in types_str for t in ["shopping_mall", "market"]): return 120
    if any(t in types_str for t in ["cafe", "restaurant", "bakery", "food"]): return 60
    return 90

def fetch_and_cache_places_from_google(city: str, keywords: list, db: Session):
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.PLACES_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.location,places.regularOpeningHours,places.types,places.rating,places.userRatingCount,places.photos"
    }

    search_queries = [f"{kw} in {city}" for kw in keywords] if keywords else [
        f"top tourist attractions in {city}",
        f"famous temples and religious places in {city}",
        f"parks, beaches, and nature spots in {city}"
    ]

    all_unique_places = {}
    seen_coords = set() # NEW: Track coordinates to prevent geo-duplicates
    
    for query in search_queries:
        payload = {"textQuery": query, "pageSize": 20, "languageCode": "en"}
        response = requests.post(url, headers=headers, json=payload, timeout=10)

        if response.status_code == 200:
            for place in response.json().get("places", []):
                place_id = place.get("id")
                lat = place.get("location", {}).get("latitude")
                lng = place.get("location", {}).get("longitude")
                
                if not lat or not lng: continue
                
                # NEW: Round coordinates to ~11 meters (4 decimal places)
                coord_key = f"{round(lat, 4)}_{round(lng, 4)}"
                
                if place_id and coord_key not in seen_coords:
                    seen_coords.add(coord_key)
                    all_unique_places[place_id] = place
        else:
            print(f"GOOGLE API WARNING: {response.text}")

    if not all_unique_places:
        raise HTTPException(status_code=500, detail="Failed to fetch any places from Google.")

    for place in all_unique_places.values():
        place_id = place.get("id")
        name = place.get("displayName", {}).get("text", "Unknown Attraction")
        lat = place.get("location", {}).get("latitude")
        lng = place.get("location", {}).get("longitude")
        
        place_types = place.get("types", [])
        duration = estimate_visit_duration(place_types)
        
        rating = place.get("rating", 0.0)
        user_ratings_total = place.get("userRatingCount", 0)
        primary_cat = place_types[0] if place_types else "attraction"
        
        photos = place.get("photos", [])
        photo_url = f"https://places.googleapis.com/v1/{photos[0].get('name')}/media?maxHeightPx=400&maxWidthPx=600&key={settings.PLACES_API_KEY}" if photos else None

        existing_loc = db.execute(text("SELECT place_id FROM locations WHERE place_id = :pid"), {"pid": place_id}).fetchone()

        if not existing_loc:
            db.execute(text("""
                INSERT INTO locations (
                    place_id, name, city, geom, weather_dependency, 
                    operating_hours, visit_duration, rating, 
                    user_ratings_total, primary_category, category_tags, photo_url
                ) VALUES (
                    :place_id, :name, :city, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), 
                    'Mixed', :hours, :duration, :rating, 
                    :ratings_total, :primary_cat, :tags, :photo_url
                )
            """), {
                "place_id": place_id, "name": name, "city": city, "lng": lng, "lat": lat,
                "hours": '{"open": "09:00", "close": "18:00"}', "duration": duration,
                "rating": rating, "ratings_total": user_ratings_total, "primary_cat": primary_cat,
                "tags": json.dumps(place_types), "photo_url": photo_url
            })
            db.commit()