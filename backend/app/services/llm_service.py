import json
from typing import List
from dotenv import load_dotenv
import google.genai as genai
from app.core.config import settings

load_dotenv()
ai_client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None


def model_text(response) -> str:
    """Concatenate only the text parts of a Gemini response.

    gemini-3.5-flash-lite returns "thinking" parts (thought_signature) next to
    the answer. Reading ``response.text`` then logs a noisy warning on every
    call ("there are non-text parts in the response"). Pulling the text from the
    parts directly returns the same JSON without the warning.
    """
    try:
        parts = response.candidates[0].content.parts or []
        chunks = [part.text for part in parts if getattr(part, "text", None)]
        if chunks:
            return "".join(chunks)
    except (AttributeError, IndexError, TypeError):
        pass
    return getattr(response, "text", "") or ""

def generate_human_storytelling(city: str, stops: List[dict]) -> dict:
    if not stops:
        return {}

    stop_names = [stop.get("name") for stop in stops if stop.get("name")]
    if not stop_names:
        return {}

    if not ai_client:
        return {name: "A curated destination matching your travel preferences." for name in stop_names}
    
    prompt = f"""
    You are an expert local tour guide for {city}.
    Given this ordered list of attractions: {stop_names}.
    
    For each attraction, provide a concise 1-2 sentence human-like guide note explaining WHY it's scheduled at this time and a key local tip.
    Return a JSON object mapping place name to the guide note string.
    """
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-3.5-flash-lite',  # Updated as requested per Google's latest migration
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'temperature': 0.7
            }
        )
        return json.loads(model_text(response))
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return {name: "Handpicked destination matching your travel style." for name in stop_names}


def curate_and_group_places_with_llm(user_keywords: List[str], candidate_places: List[dict], days_count: int) -> dict:
    """
    Asks Gemini to select the best places AND group them by day.
    Returns a dict like: {"day_1": ["place_id", ...], "day_2": [...]}
    """
    if not ai_client or not candidate_places:
        # Fallback: just split them evenly
        chunk_size = len(candidate_places) // days_count if days_count > 0 else len(candidate_places)
        return {f"day_{i+1}": [p["place_id"] for p in candidate_places[i*chunk_size:(i+1)*chunk_size]] for i in range(days_count)}

    simplified_candidates = [
        {
            "place_id": p["place_id"], "name": p["name"],
            "types": p["types"], "rating": p["rating"]
        } for p in candidate_places
    ]

    target_place_count = days_count * 6
    prompt = f"""
    You are an expert travel planner.
    User preferences: {user_keywords}
    Candidate places: {json.dumps(simplified_candidates)}
    Trip Duration: {days_count} days.

    Select the best {target_place_count} places that match the user's preferences.
    Then, divide them logically into {days_count} days. 
    Group geographically close places together, and consider time-of-day logic (e.g., beaches/sunsets in the evening, temples in the morning).
    
    Return a JSON object mapping day numbers to arrays of place_ids.
    Example format: {{"day_1": ["place_id_1", "place_id_2"], "day_2": ["place_id_3"]}}
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt,
            config={'response_mime_type': 'application/json', 'temperature': 0.4}
        )
        grouped_data = json.loads(model_text(response))
        if isinstance(grouped_data, dict) and len(grouped_data) > 0:
            print(f"DEBUG: LLM grouped places for {len(grouped_data)} days.")
            return grouped_data
        return {}
    except Exception as e:
        print(f"Gemini Curation Error: {e}")
        return {}