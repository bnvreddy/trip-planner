"""Merge near-duplicate places that are already stored.

Read-only unless ``--apply`` is passed. A merge keeps the better-rated row,
repoints any itinerary stop that used the loser, drops its cached legs (they are
per place id) and deletes the loser.

    python -m scripts.merge_duplicate_places            # report
    python -m scripts.merge_duplicate_places --apply    # merge
"""

import sys

from sqlalchemy import text

from app.db.database import engine
from app.services.place_hygiene import find_near_duplicate_pairs, merge_pairs


def main(apply: bool = False):
    with engine.begin() as conn:
        pairs = find_near_duplicate_pairs(conn)

        if not pairs:
            print("No near-duplicate places found.")
            return

        print(f"{len(pairs)} duplicate pair(s):")
        for loser, keeper, gap in pairs:
            print(f"  - '{loser.name}' ({loser.rating}) -> '{keeper.name}' ({keeper.rating}), "
                  f"{round(gap)} m apart, {loser.city}")

        if not apply:
            print("\nDry run. Re-run with --apply to merge.")
            return

        merged = merge_pairs(conn, pairs)
        places = conn.execute(text("SELECT COUNT(*) FROM locations")).scalar()
        print(f"\nMerged {merged} row(s). places now={places}")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
