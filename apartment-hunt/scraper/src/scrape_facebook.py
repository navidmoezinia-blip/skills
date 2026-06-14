"""Call Apify's Facebook Marketplace scraper and preview the results.

This is the dedicated "scrape Facebook" script. It runs the actor, saves the
raw items to data/incoming/facebook.json, and prints a quick summary of each
listing (price, beds/sqft, laundry, carpet, utilities, location).

    python src/scrape_facebook.py

Needs your Apify token in config.json ("apifyToken") or the APIFY_TOKEN env var.
The daily brief (src/daily.py) calls the same actor itself; this script is for
running/inspecting the Facebook scrape on its own.
"""

import json
import os
import sys
from pathlib import Path

import fetch_apify
from filtering import feature_summary
from sources import normalize_facebook


DEFAULT_ACTOR = "apify/facebook-marketplace-scraper"
DEFAULT_URL = "https://www.facebook.com/marketplace/galveston/propertyrentals"
OUT_PATH = Path("data/incoming/facebook.json")
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "config.json"))
EXAMPLE_CONFIG_PATH = Path("daily.config.example.json")


def main() -> int:
    config = load_config()
    token = config.get("apifyToken") or os.environ.get("APIFY_TOKEN")
    if not token:
        raise SystemExit("No Apify token. Set 'apifyToken' in config.json or the APIFY_TOKEN env var.")

    actor_id, actor_input = facebook_actor_config(config)
    print(f"Calling Apify actor '{actor_id}' ...")
    print(f"Input: {json.dumps(actor_input)}")
    records = fetch_apify.run_actor(actor_id, token, actor_input)
    print(f"Got {len(records)} raw listings.\n")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")

    budget = config.get("budget")
    for i, record in enumerate(records, start=1):
        m = normalize_facebook(record)
        text = f"{m['title']} {m['description']}"
        f = feature_summary(text, budget)
        print(f"{i:>2}. {m['title'][:64]}")
        print(f"    {summary_line(m, f)}")
        print(f"    {m['url']}")

    print(f"\nSaved raw listings to {OUT_PATH}")
    print("Next: `python src/daily.py` to filter, dedup and email the brief.")
    return 0


def facebook_actor_config(config: dict) -> tuple[str, dict]:
    fb = next((s for s in config.get("sources", []) if s.get("type") == "facebook"), {})
    apify = fb.get("apify", {}) if isinstance(fb, dict) else {}
    actor_id = apify.get("actorId") or DEFAULT_ACTOR
    if str(actor_id).startswith("REPLACE"):
        actor_id = DEFAULT_ACTOR
    actor_input = apify.get("input") or {
        "startUrls": [{"url": DEFAULT_URL}],
        "resultsLimit": 40,
        "includeListingDetails": True,
    }
    # includeListingDetails is required for descriptions (and thus filtering).
    actor_input.setdefault("includeListingDetails", True)
    return actor_id, actor_input


def summary_line(m: dict, f: dict) -> str:
    bits = [f"${m['price']:,}" if isinstance(m.get("price"), int) else "price n/a"]
    if f["utilities"] == "included":
        bits.append("utils incl")
    elif f["utilities"] == "excluded":
        bits.append("utils extra")
    if f["beds"] == 0:
        bits.append("studio")
    elif isinstance(f["beds"], int):
        bits.append(f"{f['beds']}bd")
    if f["sqft"]:
        bits.append(f"~{f['sqft']} sqft")
    bits.append("in-unit W/D" if f["inUnitLaundry"] else "laundry?")
    if f["carpet"] is True:
        bits.append("no carpet")
    elif f["carpet"] is False:
        bits.append("has carpet")
    if m.get("location"):
        bits.append(m["location"])
    return " · ".join(bits)


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
