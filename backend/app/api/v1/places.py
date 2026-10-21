from fastapi import APIRouter

router = APIRouter()

@router.get("/keywords")
def get_keyword_categories():
    return {
        "categories": {
            "Culture & Spiritual": ["Ancient Temples", "Heritage Sites", "Ashrams", "Architecture"],
            "Nature & Outdoors": ["Beaches", "Waterfalls", "Hill Stations", "Parks & Gardens"],
            "Leisure & Food": ["Local Bazaars", "Street Food", "Museums", "Viewpoints"],
            "History & Heritage": ["Forts", "Palaces", "Archaeological Sites", "Monuments"]
        }
    }