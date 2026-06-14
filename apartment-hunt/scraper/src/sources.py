"""Per-source normalizers: turn each site's raw records into our internal shape.

Internal listing dict:
    {id, source, title, price, currency, location, url, image,
     description, beds, sqft, postedAt}

Field names differ per Apify actor / site, so each normalizer tries the common
names with fallbacks. Confirm against your chosen actors' real output.
"""

import re

from filtering import extract_beds, extract_sqft, first_price, listing_id_from_url
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
        return parse_price(pick(value, "amount", "value", "price", "formatted_amount"))
    # Plain number ("1150"), "$1,150", "1150/mo" — grab the first integer.
    m = re.search(r"([0-9][0-9,]*)", str(value))
    return int(m.group(1).replace(",", "")) if m else None


def parse_location(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # FB often nests: location.reverse_geocode.city_page.display_name
        rg = value.get("reverse_geocode") or value.get("reverse_geocode_detailed") or {}
        if isinstance(rg, dict):
            disp = pick(rg.get("city_page", {}) if isinstance(rg.get("city_page"), dict) else {}, "display_name")
            if disp:
                return str(disp)
            city = pick(rg, "city", "name")
            st = pick(rg, "state", "state_code")
            if city or st:
                return ", ".join(p for p in (str(city) if city else "", str(st) if st else "") if p)
        city = pick(value, "city", "displayName", "display_name", "name", "text", "addressLocality")
        st = pick(value, "state", "stateCode", "region", "addressRegion")
        return ", ".join(p for p in (str(city) if city else "", str(st) if st else "") if p)
    return str(value)


def parse_text_field(value) -> str:
    """FB description often arrives as {'text': '...'}."""
    if isinstance(value, dict):
        return str(pick(value, "text", "plaintext", "value") or "")
    return str(value or "")


def parse_photo(value) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if value.get("photo_image_url"):
            return value["photo_image_url"]
        img = value.get("image") if isinstance(value.get("image"), dict) else None
        return pick(img or value, "uri", "url", "src", "photo_image_url")
    return None


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
    """Maps the official apify/facebook-marketplace-scraper output (with
    includeListingDetails enabled). Falls back to other field names too."""
    url = pick(record, "itemUrl", "listingUrl", "url", "link") or ""
    out = _base(record, "facebook", url)
    out["id"] = str(pick(record, "id", "listingId", "facebookId", "itemId") or listing_id_from_url(url) or "")
    title = clean_text(pick(record, "listingTitle", "marketplace_listing_title", "title", "name"))
    out["title"] = title.replace("+", " ") if title else "Marketplace listing"
    out["price"] = parse_price(pick(record, "listingPrice", "listing_price", "price", "amount", "formattedPrice"))
    out["location"] = clean_text(parse_location(pick(record, "location", "address", "city", "place")))
    out["image"] = parse_photo(pick(record, "primary_listing_photo", "image", "imageUrl", "primaryImage", "photo")) or out["image"]
    out["description"] = clean_text(
        parse_text_field(pick(record, "redacted_description", "description", "redactedDescription", "body"))
    )
    if out["price"] is None:
        out["price"] = first_price(out["title"]) or first_price(out["description"])

    text = f"{out['title']} {out['description']}"
    out["beds"] = out["beds"] if out["beds"] is not None else extract_beds(text)
    out["sqft"] = out["sqft"] if out["sqft"] is not None else extract_sqft(text)
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
