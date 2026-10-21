"""Collapse the near-duplicate POIs Google returns for a single site.

The Places API happily returns "Bhavani Island" and "Bhavani Island Park" as
two POIs 270 m apart, and "Kanaka Durga Temple" next to
"Kanaka Durga Temple, Indhrakeeladhri". Coordinate rounding cannot catch that,
so identity is decided on normalized names within a short radius.
"""

import math
import re

NOISE_TOKENS = {
    "sri", "sree", "shri", "shree", "the", "of", "and", "at", "in", "de",
}

NEAR_DUPLICATE_RADIUS_METERS = 400


def normalize_name(name: str) -> list:
    cleaned = re.sub(r"[^0-9a-z]+", " ", (name or "").lower())
    return [token for token in cleaned.split() if token and token not in NOISE_TOKENS]


def names_likely_same(name_a: str, name_b: str) -> bool:
    tokens_a, tokens_b = normalize_name(name_a), normalize_name(name_b)
    if not tokens_a or not tokens_b:
        return False

    joined_a, joined_b = " ".join(tokens_a), " ".join(tokens_b)
    if joined_a == joined_b:
        return True
    if joined_a in joined_b or joined_b in joined_a:
        return True

    # Spelling variants of one name: "Kailasa Giri" vs "Kailasagiri Hilltop Park"
    # differ as word tokens but collapse once spaces are removed.
    squashed_a, squashed_b = "".join(tokens_a), "".join(tokens_b)
    if min(len(squashed_a), len(squashed_b)) >= 8 and (
        squashed_a in squashed_b or squashed_b in squashed_a
    ):
        return True

    # One dominant long word inside a decorated name: "VMRDA-Kailasagiri" is the
    # same hill as "Kailasagiri Hilltop Park". The word has to dominate the
    # shorter name, otherwise "Ramakrishna Beach" would swallow every beach.
    short_length = min(len(squashed_a), len(squashed_b))
    for token in tokens_a:
        if len(token) >= 8 and token in squashed_b and len(token) >= 0.6 * short_length:
            return True
    for token in tokens_b:
        if len(token) >= 8 and token in squashed_a and len(token) >= 0.6 * short_length:
            return True

    shared = set(tokens_a) & set(tokens_b)
    union = set(tokens_a) | set(tokens_b)
    return len(shared) >= 2 and len(shared) / len(union) >= 0.6


def distance_meters(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    radius = 6371000.0
    phi_a, phi_b = math.radians(lat_a), math.radians(lat_b)
    d_phi = phi_b - phi_a
    d_lambda = math.radians(lng_b - lng_a)
    hav = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(hav))


def collapse_near_duplicates(rows, radius_meters: int = NEAR_DUPLICATE_RADIUS_METERS):
    """Keep the best-rated row of each near-duplicate cluster.

    Returns ``(kept_rows, dropped)`` where ``dropped`` lists
    ``{"place_name", "duplicate_of"}`` for transparency in the API response.
    Nothing is written to the database here -- this only shapes the candidate
    pool for one trip.
    """
    ordered = sorted(rows, key=lambda row: (float(row.rating or 0)), reverse=True)
    kept = []
    dropped = []

    for row in ordered:
        duplicate_of = None
        for existing in kept:
            gap = distance_meters(
                float(row.lat), float(row.lng), float(existing.lat), float(existing.lng)
            )
            if gap <= radius_meters and names_likely_same(row.name, existing.name):
                duplicate_of = existing.name
                break

        if duplicate_of:
            dropped.append({
                "place_name": row.name,
                "duplicate_of": duplicate_of,
            })
        else:
            kept.append(row)

    return kept, dropped
