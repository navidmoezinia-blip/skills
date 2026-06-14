"""Pure filtering / brief logic — no Playwright, no network.

Shared by the Apify digest pipeline. Operates on a normalized listing dict:
    {id, title, price, currency, location, url, image, description, postedAt}
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #
def normalize(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def first_price(text) -> int | None:
    match = re.search(r"\$\s?([0-9][0-9,]*)", str(text or ""))
    return int(match.group(1).replace(",", "")) if match else None


def contains_word(text: str, term: str, allow_negated: bool = True) -> bool:
    """Word-boundary match. With allow_negated=False, an occurrence immediately
    preceded by no/non/without/not does NOT count (so "no carpet" != "carpet")."""
    term = term.lower().strip()
    if not term:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
    if allow_negated:
        return re.search(pattern, text) is not None
    for m in re.finditer(pattern, text):
        prefix = text[max(0, m.start() - 14): m.start()]
        if re.search(r"\b(no|non|without|not|excludes?)\b[\s\-]*$", prefix):
            continue
        return True
    return False


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
def matches_criteria(text: str, price: int | None, criteria: dict) -> dict:
    lower = text.lower()

    for word in criteria.get("excludeAny", []):
        if contains_word(lower, str(word), allow_negated=False):
            return {"ok": False, "reason": f'excluded by "{word}"'}

    # Positive requirements are negation-aware too: "no in unit washer" must NOT
    # satisfy an "in unit" requirement.
    for word in criteria.get("includeAll", []):
        if not contains_word(lower, str(word), allow_negated=False):
            return {"ok": False, "reason": f'missing required "{word}"'}

    include_any = criteria.get("includeAny", [])
    if include_any and not any(
        contains_word(lower, str(w), allow_negated=False) for w in include_any
    ):
        return {"ok": False, "reason": "no laundry/include term found"}

    min_price = criteria.get("minPrice")
    max_price = criteria.get("maxPrice")
    if min_price is not None and price is not None and price < min_price:
        return {"ok": False, "reason": f"price {price} below min {min_price}"}
    if max_price is not None and price is not None and price > max_price:
        return {"ok": False, "reason": f"price {price} above max {max_price}"}

    return {"ok": True, "reason": None}


DEFAULT_UTIL_INCLUDED = [
    "utilities included", "utils included", "all bills paid",
    "includes utilities", "water included", "electric included",
]
DEFAULT_UTIL_EXCLUDED = [
    "tenant pays", "plus utilities", "+ utilities", "utilities not included",
    "excludes utilities", "pay your own", "not included",
]


def utilities_status(text: str, budget: dict | None) -> str:
    """Return 'included' / 'excluded' / 'unknown'."""
    low = text.lower()
    included = (budget or {}).get("utilitiesIncludedPhrases", DEFAULT_UTIL_INCLUDED)
    excluded = (budget or {}).get("utilitiesExcludedPhrases", DEFAULT_UTIL_EXCLUDED)
    if any(p.lower() in low for p in included):
        return "included"
    if any(p.lower() in low for p in excluded):
        return "excluded"
    return "unknown"


def utilities_included(text: str, budget: dict | None) -> bool:
    return utilities_status(text, budget) == "included"


def budget_check(text: str, price: int | None, budget: dict | None) -> tuple[bool, str | None]:
    """<= withUtilitiesMax if utilities included; <= withoutUtilitiesMax if
    explicitly excluded; if unknown, use the higher cap (don't hard-drop).
    Unknown price is never dropped."""
    if not budget or price is None:
        return True, None
    status = utilities_status(text, budget)
    if status == "excluded":
        cap = budget.get("withoutUtilitiesMax", 1000)
    else:  # included or unknown -> generous cap
        cap = budget.get("withUtilitiesMax", 1200)
    if cap is not None and price > cap:
        return False, f"price ${price} over ${cap} (utils {status})"
    return True, None


# --------------------------------------------------------------------------- #
# State / dedup
# --------------------------------------------------------------------------- #
def listing_id_from_url(url: str) -> str | None:
    match = re.search(r"/marketplace/item/([^/?#]+)", str(url or ""))
    return match.group(1) if match else None


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"seen": {}}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"seen": {str(k): {"url": str(k)} for k in loaded}}
    if not isinstance(loaded, dict):
        return {"seen": {}}
    loaded.setdefault("seen", {})
    return loaded


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)  # atomic on the same filesystem


def remember_seen(state: dict, key: str, listing: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    prior = state["seen"].get(key, {})
    state["seen"][key] = {
        "url": listing.get("url"),
        "price": listing.get("price"),
        "firstSeenAt": prior.get("firstSeenAt", now),
        "lastSeenAt": now,
    }


def prior_price(state: dict, key: str) -> int | None:
    entry = state["seen"].get(key) or {}
    return entry.get("price")
