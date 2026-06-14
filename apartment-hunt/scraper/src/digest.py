"""Apify -> apartment digest.

Reads Facebook Marketplace listings that an Apify actor produced (a JSON array,
from a file or stdin), filters them against your criteria + budget rule, drops
already-seen ones, and writes a brief (max N listings) you can email.

    python src/digest.py path/to/apify-results.json
    apify ... | python src/digest.py            # or pipe the JSON in

No browser, no Facebook login — Apify already did the scraping.

NOTE: `normalize_apify()` maps Apify's fields into our internal shape. Field
names vary per actor, so confirm/adjust it against YOUR actor's real output
(send me a sample and I'll lock it in).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from filtering import (
    budget_check,
    first_price,
    listing_id_from_url,
    load_state,
    matches_criteria,
    normalize,
    prior_price,
    remember_seen,
    save_state,
    utilities_included,
)


CONFIG_PATH = Path("config.json")
EXAMPLE_CONFIG_PATH = Path("digest.config.example.json")
LOG_DIR = Path("logs")
DEFAULT_STATE_PATH = Path("data/seen-listings.json")


def main(argv: list[str]) -> int:
    config = load_config()
    records = load_records(argv)
    state_path = Path(config.get("stateFile") or DEFAULT_STATE_PATH)
    state = load_state(state_path)

    budget = config.get("budget")
    criteria = config.get("criteria", {})
    only_new = config.get("onlyNewListings", True)

    report = {
        "scanned": len(records),
        "new": 0,
        "alreadySeen": 0,
        "matched": 0,
        "priceDrops": 0,
        "skipped": [],
        "matches": [],
    }

    for record in records:
        listing = normalize_apify(record)
        key = listing["id"] or listing_id_from_url(listing["url"]) or listing["url"]
        if not key:
            continue

        seen_before = key in state["seen"]
        if only_new and seen_before:
            # Still surface a price drop on a listing we've seen.
            old = prior_price(state, key)
            if old is not None and listing["price"] is not None and listing["price"] < old:
                report["priceDrops"] += 1
                listing["priceDropFrom"] = old
                report["matches"].append(listing)
            report["alreadySeen"] += 1
            remember_seen(state, key, listing)
            continue

        report["new"] += 1
        text = f"{listing['title']} {listing['description']}"

        crit = matches_criteria(text, listing["price"], criteria)
        if not crit["ok"]:
            report["skipped"].append({"url": listing["url"], "reason": crit["reason"]})
            remember_seen(state, key, listing)
            continue

        ok, reason = budget_check(text, listing["price"], budget)
        if not ok:
            report["skipped"].append({"url": listing["url"], "reason": reason})
            remember_seen(state, key, listing)
            continue

        listing["isNew"] = not seen_before
        listing["utilitiesIncluded"] = utilities_included(text, budget)
        report["matched"] += 1
        report["matches"].append(listing)
        remember_seen(state, key, listing)

    ranked = rank(report["matches"])
    limit = int(config.get("briefMaxListings", 5))
    brief = render_brief(report, ranked, limit)

    save_state(state_path, state)
    write_outputs(report, brief)
    print(brief)
    return 0


# --------------------------------------------------------------------------- #
# Apify field mapping  (CONFIRM AGAINST YOUR ACTOR)
# --------------------------------------------------------------------------- #
def normalize_apify(record: dict) -> dict:
    """Map an Apify FB Marketplace record into our internal listing shape.
    Tries the common field names used by popular actors, with fallbacks."""
    url = (
        pick(record, "url", "listingUrl", "facebookUrl", "link")
        or ""
    )
    listing_id = str(
        pick(record, "id", "listingId", "facebookId", "itemId")
        or listing_id_from_url(url)
        or ""
    )
    title = normalize(pick(record, "title", "marketplace_listing_title", "name", "heading"))
    description = normalize(
        pick(record, "description", "redactedDescription", "listingDescription", "body")
    )

    price = parse_price(pick(record, "price", "listingPrice", "amount", "formattedPrice"))
    if price is None:
        price = first_price(title) or first_price(description)

    location = normalize(parse_location(pick(record, "location", "city", "locationText", "place")))
    image = pick(record, "image", "imageUrl", "primaryImage", "photo", "thumbnail")
    posted = pick(record, "postedAt", "creationTime", "creation_time", "listedTime", "createdAt")

    return {
        "id": listing_id,
        "title": title or "Marketplace listing",
        "price": price,
        "currency": pick(record, "currency") or "USD",
        "location": location,
        "url": url,
        "image": image,
        "description": description,
        "postedAt": posted,
    }


def pick(record: dict, *keys):
    for key in keys:
        if isinstance(record, dict) and record.get(key) not in (None, ""):
            return record[key]
    return None


def parse_price(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, dict):  # e.g. {"amount": "1200", "currency": "USD"}
        return parse_price(pick(value, "amount", "value", "price"))
    return first_price(str(value))


def parse_location(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):  # e.g. {"city": "Galveston", "state": "TX"}
        city = pick(value, "city", "displayName", "name", "text")
        st = pick(value, "state", "stateCode", "region")
        return ", ".join(p for p in (str(city) if city else "", str(st) if st else "") if p)
    return str(value)


# --------------------------------------------------------------------------- #
# Rank + render
# --------------------------------------------------------------------------- #
def rank(matches: list[dict]) -> list[dict]:
    # New first, then price-drops, then cheapest. (Bougie/commute enrichment is
    # a later LLM step; until then, cheaper-and-newer floats up.)
    def key(m):
        return (
            0 if m.get("isNew") else 1,
            0 if m.get("priceDropFrom") else 1,
            m.get("price") if m.get("price") is not None else 10**9,
        )
    return sorted(matches, key=key)


def render_brief(report: dict, ranked: list[dict], limit: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# 🏠 Apartment Hunt — {now}",
        "",
        f"- Listings scanned: {report['scanned']}",
        f"- New this run: {report['new']}",
        f"- Matches: {report['matched']}   |   Price drops: {report['priceDrops']}",
        "",
        f"## Top {min(limit, len(ranked))} listings",
        "",
    ]
    if not ranked:
        lines.append("No matching listings this run.")
    else:
        for i, m in enumerate(ranked[:limit], start=1):
            price = f"${m['price']:,}" if m.get("price") is not None else "Price n/a"
            util = " · utils incl" if m.get("utilitiesIncluded") else ""
            loc = f" · {m['location']}" if m.get("location") else ""
            tags = []
            if m.get("isNew"):
                tags.append("NEW")
            if m.get("priceDropFrom"):
                tags.append(f"PRICE DROP from ${m['priceDropFrom']:,}")
            tag = f"  _({', '.join(tags)})_" if tags else ""
            lines += [
                f"{i}. [{m['title']}]({m['url']}){tag}",
                f"   {price}{util}{loc}",
                "",
            ]
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(report: dict, brief: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat().replace(":", "-").replace(".", "-")
    (LOG_DIR / f"run-{stamp}.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (LOG_DIR / f"brief-{stamp}.md").write_text(brief, encoding="utf-8")


# --------------------------------------------------------------------------- #
# IO
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))


def load_records(argv: list[str]) -> list[dict]:
    raw = Path(argv[1]).read_text(encoding="utf-8") if len(argv) > 1 else sys.stdin.read()
    data = json.loads(raw)
    if isinstance(data, dict):
        # Apify sometimes wraps results under "items" / "results".
        data = data.get("items") or data.get("results") or [data]
    return [r for r in data if isinstance(r, dict)]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
