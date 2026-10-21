"""Which requested vibes the stored catalogue can actually satisfy.

The rule is: reuse the database, but never let a keyword silently produce
nothing. If a selected keyword has no matching place in that city, the caller
fetches from Google -- for that keyword only, not the whole set.
"""

import re

from sqlalchemy import text

# The keyword catalogue from /keywords, mapped to the terms Google actually
# returns (categories, tags and place names are all searched).
KEYWORD_TERMS = {
    "Ancient Temples": ["temple", "hindu_temple", "devasthanam", "shrine", "mandir"],
    "Heritage Sites": ["heritage", "historic", "historical_landmark", "monument", "archaeological"],
    "Ashrams": ["ashram", "math", "mutt", "spiritual"],
    "Architecture": ["architecture", "palace", "fort", "monument", "historic"],
    "Beaches": ["beach", "coast", "shore"],
    "Waterfalls": ["waterfall", "falls", "cascade"],
    "Hill Stations": ["hill", "mountain", "peak", "viewpoint"],
    "Parks & Gardens": ["park", "garden", "botanical"],
    "Local Bazaars": ["market", "bazaar", "shopping_mall"],
    "Street Food": ["restaurant", "cafe", "food", "bakery", "street_food"],
    "Museums": ["museum", "gallery"],
    "Viewpoints": ["viewpoint", "observation", "lookout"],
    "Forts": ["fort", "fortress", "citadel"],
    "Palaces": ["palace", "mahal"],
    "Archaeological Sites": ["archaeological", "ruins", "cave", "excavation"],
    "Monuments": ["monument", "memorial", "landmark", "statue"],
}

MIN_TERM_LENGTH = 4


def terms_for(keyword: str) -> list:
    """Mapped terms, or the keyword's own significant words as a fallback."""
    mapped = KEYWORD_TERMS.get(keyword)
    if mapped:
        return mapped

    words = [word for word in re.split(r"[^a-z0-9]+", keyword.lower()) if len(word) >= MIN_TERM_LENGTH]
    return words or [keyword.lower()]


def is_keyword_covered(db, city: str, keyword: str) -> bool:
    """True when at least one stored place in this city matches the keyword."""
    terms = terms_for(keyword)
    clauses = " OR ".join(
        f"""(
            lower(COALESCE(primary_category, '')) LIKE :t{index}
            OR lower(name) LIKE :t{index}
            OR lower(COALESCE(category_tags::text, '')) LIKE :t{index}
        )"""
        for index in range(len(terms))
    )

    params = {"city": city}
    for index, term in enumerate(terms):
        params[f"t{index}"] = f"%{term.lower()}%"

    found = db.execute(
        text(f"SELECT 1 FROM locations WHERE city = :city AND ({clauses}) LIMIT 1"),
        params,
    ).fetchone()
    return found is not None


def uncovered_keywords(db, city: str, keywords) -> list:
    """Keywords the stored catalogue cannot serve, in the order they were given."""
    return [keyword for keyword in (keywords or []) if not is_keyword_covered(db, city, keyword)]
