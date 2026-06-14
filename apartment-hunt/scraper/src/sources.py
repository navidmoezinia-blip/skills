"""Per-source normalizers: turn each site's raw records into our internal shape.

Internal listing dict:
    {id, source, title, price, currency, location, url, image,
     description, beds, sqft, postedAt}

Field names differ per Apify actor / site, so each normalizer tries the common
names with fallbacks. Confirm against your chosen actors' real output.
"""

from filtering import first_price, listing_id_from_url
from filtering import normalize as clean_text


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
    if isinstance(value, dict):
        return parse_price(pick(value, "amount", "value", "price"))
    return first_price(str(value))


def parse_location(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        city = pick(value, "city", "displayName", "name", "text", "addressLocality")
        st = pick(value, "state", "stateCode", "region", "addressRegion")
        return ", ".join(p for p in (str(city) if city else "", str(st) if st else "") if p)
    return str(value)


def _base(record: dict, source: str, url: str) -> dict:
    return {
        "id": "",
        "source": source,
        "title": clean_text(pick(record, "title", "name", "heading", "marketplace_listing_title")) or "Listing",
        "price": None,
        "currency": pick(record, "currency") or "USD",
        "location": clean_text(parse_location(pick(record, "location", "address", "city", "place"))),
        "url": url or "",
        "image": pick(record, "image", "imageUrl", "primaryImage", "photo", "thumbnail", "imgSrc"),
        "description": clean_text(pick(record, "description", "redactedDescription", "body", "snippet")),
        "beds": pick(record, "beds", "bedrooms", "numberOfBedrooms"),
        "sqft": pick(record, "sqft", "area", "livingArea", "squareFeet"),
        "postedAt": pick(record, "postedAt", "creationTime", "creation_time", "listedTime", "createdAt", "datePosted"),
    }


def normalize_facebook(record: dict) -> dict:
    url = pick(record, "url", "listingUrl", "facebookUrl", "link") or ""
    out = _base(record, "facebook", url)
    out["id"] = str(pick(record, "id", "listingId", "facebookId", "itemId") or listing_id_from_url(url) or "")
    out["price"] = parse_price(pick(record, "price", "listingPrice", "amount", "formattedPrice"))
    if out["price"] is None:
        out["price"] = first_price(out["title"]) or first_price(out["description"])
    return out


def normalize_generic(record: dict, source: str) -> dict:
    """For apartment sites (Apartments.com, Zillow, etc.) scraped via Apify."""
    url = pick(record, "url", "detailUrl", "listingUrl", "link", "href") or ""
    out = _base(record, source, url)
    out["id"] = str(pick(record, "id", "zpid", "listingId") or url or "")
    out["price"] = parse_price(pick(record, "price", "rent", "rentPrice", "minRent", "formattedPrice", "statusText"))
    if out["price"] is None:
        out["price"] = first_price(out["title"]) or first_price(out["description"])
    return out


def normalize_record(record: dict, source_type: str, source_name: str) -> dict:
    if source_type == "facebook":
        return normalize_facebook(record)
    return normalize_generic(record, source_name)
