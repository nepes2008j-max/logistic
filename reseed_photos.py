"""Replace the weakest listing photographs with tighter ones.

The bulk seeder searches Wikimedia Commons on a per-listing keyword, and
several of those keywords were broad enough to return a scene rather than the
object: "Shop Shelving, 6 Bays" came back as people sitting in a market stall,
"Display Fridge, 400L" as a wall of souvenir magnets. The layout around the
cards is disciplined and the contents looked like a junk drawer.

This re-fetches only the listings named below, with a keyword describing the
object on a plain ground, and only replaces the file when the new one actually
arrives. Everything else is left alone.

    .venv/bin/python reseed_photos.py            # the listed ones
    .venv/bin/python reseed_photos.py 105 104    # specific item ids

Commons rate-limits a burst, so a run that reports misses is worth repeating —
nothing is destroyed on a miss, the old photograph stays.
"""

import os
import sys

from seed_demo_data import commons_search, _curl, IMAGE_DIR, WEB_PREFIX, slugify
from app import app, db, Item

# item id -> a search term that describes the object, not the setting
BETTER_TERMS = {
    105: "metal shelf unit",
    104: "refrigerator white appliance isolated",
    103: "thermal receipt printer",
    102: "electric shaver razor",
    101: "massage gun percussion device",
    100: "hairdryer",
    99:  "cat tree scratching post",
    98:  "glass aquarium fish tank",
    97:  "dog crate cage",
    96:  "greenhouse polycarbonate garden",
    95:  "garden table chairs patio furniture",
    94:  "lawn mower petrol garden",
    93:  "dutar instrument",
    92:  "digital piano keyboard instrument",
    91:  "acoustic guitar instrument",
    90:  "fishing rod reel",
    89:  "dumbbell weights",
    88:  "camping tent outdoor",
}


def looks_like_image(path):
    if not os.path.exists(path) or os.path.getsize(path) < 12000:
        return False
    with open(path, "rb") as handle:
        head = handle.read(4)
    return head[:3] == b"\xff\xd8\xff" or head[:4] == b"\x89PNG"


def reseed(item, term):
    """Fetch into a temporary name, and only swap it in if it arrived."""
    os.makedirs(IMAGE_DIR, exist_ok=True)
    final = os.path.join(IMAGE_DIR, "seed_%s.jpg" % slugify(item.title))
    staging = final + ".new"

    for url in commons_search(term, limit=6):
        if _curl(url, staging) and looks_like_image(staging):
            os.replace(staging, final)
            item.image_url = WEB_PREFIX + os.path.basename(final)
            return True
        if os.path.exists(staging):
            os.remove(staging)
    return False


def main():
    wanted = [int(a) for a in sys.argv[1:]] or sorted(BETTER_TERMS)
    replaced, missed = 0, []

    with app.app_context():
        for item_id in wanted:
            term = BETTER_TERMS.get(item_id)
            item = db.session.get(Item, item_id)
            if not item or not term:
                continue
            if reseed(item, term):
                db.session.commit()
                replaced += 1
                print("  ok    %-34s %s" % (item.title[:34], term))
            else:
                missed.append(item.title)
                print("  MISS  %-34s (keeping the old photograph)" % item.title[:34])

    print("\nreplaced %d, missed %d" % (replaced, len(missed)))
    if missed:
        print("run it again — Commons rate-limits a burst and nothing was lost")


if __name__ == "__main__":
    main()
