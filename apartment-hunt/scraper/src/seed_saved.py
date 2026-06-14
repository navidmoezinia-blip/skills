"""Seed already-saved Facebook listing IDs into the dedup state so the daily
brief only surfaces listings ADDITIONAL to what you've already saved.

    python src/seed_saved.py            # reads saved-fb-ids.txt
    python src/seed_saved.py myids.txt
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

from filtering import load_state, save_state


DEFAULT_IDS_FILE = Path("saved-fb-ids.txt")
DEFAULT_STATE_PATH = Path("data/seen-listings.json")


def main(argv: list[str]) -> int:
    ids_file = Path(argv[1]) if len(argv) > 1 else DEFAULT_IDS_FILE
    ids = [
        line.strip()
        for line in ids_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    state = load_state(DEFAULT_STATE_PATH)
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    for listing_id in ids:
        if listing_id not in state["seen"]:
            added += 1
        prior = state["seen"].get(listing_id, {})
        state["seen"][listing_id] = {
            "url": f"https://www.facebook.com/marketplace/item/{listing_id}",
            "price": prior.get("price"),
            "firstSeenAt": prior.get("firstSeenAt", now),
            "lastSeenAt": now,
            "source": "saved-seed",
        }

    save_state(DEFAULT_STATE_PATH, state)
    print(f"Seeded {len(ids)} saved listings ({added} new) into {DEFAULT_STATE_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
