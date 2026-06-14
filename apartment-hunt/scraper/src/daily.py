"""Daily apartment digest orchestrator (runs on your PC at 10am).

For each configured source (Facebook via Apify, apartment sites via Apify),
fetch -> normalize -> filter (budget/keywords) -> drop already-seen -> rank ->
take the top N for that source. Aggregate into one brief and email it.

    python src/daily.py

Pure standard library. Configure sources + email in config.json (see
daily.config.example.json). Run src/seed_saved.py once first so listings you've
already saved are excluded.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from filtering import (
    budget_check,
    listing_id_from_url,
    load_state,
    matches_criteria,
    prior_price,
    remember_seen,
    save_state,
    utilities_included,
)
from sources import normalize_record

import fetch_apify
import send_email


CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "config.json"))
EXAMPLE_CONFIG_PATH = Path("daily.config.example.json")
LOG_DIR = Path("logs")
DEFAULT_STATE_PATH = Path("data/seen-listings.json")


def main() -> int:
    config = load_config()
    state_path = Path(config.get("stateFile") or DEFAULT_STATE_PATH)
    state = load_state(state_path)
    token = config.get("apifyToken") or os.environ.get("APIFY_TOKEN", "")

    sections = []          # [{name, listings:[...]}]
    price_drops = []
    summary = {}
    errors = []

    for source in config.get("sources", []):
        name = source.get("name", "source")
        stype = source.get("type", "generic")
        cap = int(source.get("max", 2))
        try:
            records = get_records(source, token)
        except Exception as exc:  # noqa: BLE001 - one bad source shouldn't kill the run
            errors.append(f"{name}: {exc}")
            summary[name] = {"scanned": 0, "matched": 0, "shown": 0, "error": str(exc)}
            continue

        matched = []
        for record in records:
            listing = normalize_record(record, stype, name)
            key = listing["id"] or listing_id_from_url(listing["url"]) or listing["url"]
            if not key:
                continue

            if config.get("onlyNewListings", True) and key in state["seen"]:
                old = prior_price(state, key)
                if old is not None and listing["price"] is not None and listing["price"] < old:
                    listing["priceDropFrom"] = old
                    price_drops.append(listing)
                remember_seen(state, key, listing)
                continue

            text = f"{listing['title']} {listing['description']}"
            if not passes_filters(text, listing, source, config):
                remember_seen(state, key, listing)
                continue

            listing["isNew"] = True
            listing["utilitiesIncluded"] = utilities_included(text, config.get("budget"))
            matched.append(listing)
            remember_seen(state, key, listing)

        ranked = rank(matched)
        shown = ranked[:cap]
        sections.append({"name": name, "listings": shown})
        summary[name] = {"scanned": len(records), "matched": len(matched), "shown": len(shown)}

    save_state(state_path, state)

    md, html = render(sections, price_drops, summary, errors)
    total = sum(len(s["listings"]) for s in sections)
    write_outputs(md, {"summary": summary, "errors": errors, "total": total})
    print(md)

    maybe_email(config, total, md, html)
    return 0


# --------------------------------------------------------------------------- #
# Fetch + filter
# --------------------------------------------------------------------------- #
def get_records(source: dict, token: str) -> list[dict]:
    if source.get("file"):  # local JSON for testing
        data = json.loads(Path(source["file"]).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("items") or data.get("results") or [data]
        return [r for r in data if isinstance(r, dict)]
    apify = source.get("apify")
    if apify and apify.get("actorId") and not str(apify["actorId"]).startswith("REPLACE"):
        return fetch_apify.run_actor(apify["actorId"], token, apify.get("input"), apify.get("timeout", 300))
    return []  # not configured yet -> no-op (lets you add sources incrementally)


def passes_filters(text: str, listing: dict, source: dict, config: dict) -> bool:
    criteria = source.get("criteria", config.get("criteria", {}))
    require_keywords = source.get("requireKeywords", source.get("type") == "facebook")

    if require_keywords:
        if not matches_criteria(text, listing["price"], criteria)["ok"]:
            return False
    else:
        # Apartment-site actors often have sparse descriptions; apply price only.
        price = listing["price"]
        mn, mx = criteria.get("minPrice"), criteria.get("maxPrice")
        if mn is not None and price is not None and price < mn:
            return False
        if mx is not None and price is not None and price > mx:
            return False

    ok, _ = budget_check(text, listing["price"], config.get("budget"))
    return ok


def rank(matches: list[dict]) -> list[dict]:
    return sorted(matches, key=lambda m: m.get("price") if m.get("price") is not None else 10**9)


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def render(sections, price_drops, summary, errors) -> tuple[str, str]:
    date = datetime.now(timezone.utc).astimezone().strftime("%a %b %d, %Y")
    md = [f"# 🏠 Apartment Hunt — {date}", ""]
    html = [
        "<div style=\"font-family:Segoe UI,Arial,sans-serif;max-width:680px\">",
        f"<h1 style=\"font-size:22px\">🏠 Apartment Hunt — {date}</h1>",
    ]

    any_listings = False
    for section in sections:
        md.append(f"## {section['name']}")
        html.append(f"<h2 style=\"font-size:17px;margin-top:18px\">{esc(section['name'])}</h2>")
        if not section["listings"]:
            md.append("_(nothing new)_\n")
            html.append("<p style=\"color:#777\"><i>nothing new</i></p>")
            continue
        any_listings = True
        for i, m in enumerate(section["listings"], start=1):
            md.append(card_md(i, m))
            html.append(card_html(m))
        md.append("")

    if price_drops:
        md.append("## 💸 Price drops on listings you've seen")
        html.append("<h2 style=\"font-size:17px;margin-top:18px\">💸 Price drops</h2>")
        for m in price_drops:
            md.append(f"- [{m['title']}]({m['url']}) — now {money(m['price'])} (was {money(m['priceDropFrom'])})")
            html.append(
                f"<p><a href=\"{esc(m['url'])}\">{esc(m['title'])}</a> — now "
                f"{money(m['price'])} (was {money(m['priceDropFrom'])})</p>"
            )

    if not any_listings and not price_drops:
        md.append("_No new matching listings today._")
        html.append("<p>No new matching listings today.</p>")

    if errors:
        md.append("\n---\n_Source errors: " + "; ".join(errors) + "_")
        html.append("<hr><p style=\"color:#a00;font-size:12px\">Source errors: " + esc("; ".join(errors)) + "</p>")

    html.append("</div>")
    return "\n".join(md).rstrip() + "\n", "\n".join(html)


def card_md(i, m) -> str:
    bits = [money(m.get("price"))]
    if m.get("utilitiesIncluded"):
        bits.append("utils incl")
    if m.get("location"):
        bits.append(m["location"])
    return f"{i}. [{m['title']}]({m['url']})\n   " + " · ".join(b for b in bits if b)


def card_html(m) -> str:
    bits = [money(m.get("price"))]
    if m.get("utilitiesIncluded"):
        bits.append("utils incl")
    if m.get("location"):
        bits.append(esc(m["location"]))
    sub = " · ".join(b for b in bits if b)
    img = f"<img src=\"{esc(m['image'])}\" width=\"120\" style=\"border-radius:6px;float:left;margin:0 10px 8px 0\">" if m.get("image") else ""
    return (
        "<div style=\"border:1px solid #e2e2e2;border-radius:8px;padding:10px;margin:8px 0;overflow:hidden\">"
        f"{img}<a href=\"{esc(m['url'])}\" style=\"font-weight:600;font-size:15px\">{esc(m['title'])}</a>"
        f"<div style=\"color:#444;margin-top:4px\">{sub}</div></div>"
    )


def money(value) -> str:
    return f"${value:,}" if isinstance(value, int) else "Price n/a"


def esc(value) -> str:
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# --------------------------------------------------------------------------- #
# IO
# --------------------------------------------------------------------------- #
def maybe_email(config: dict, total: int, md: str, html: str) -> None:
    email = config.get("email", {})
    if not email.get("enabled"):
        print("(email disabled — brief written to logs/ only)")
        return
    subject = f"🏠 Apartment Hunt — {total} new ({datetime.now().astimezone().strftime('%b %d')})"
    try:
        send_email.send(
            subject, html, md, email["to"], email["gmailUser"], email["appPassword"]
        )
        print(f"Emailed {total} listings to {email['to']}.")
    except Exception as exc:  # noqa: BLE001
        print(f"EMAIL FAILED: {exc}")


def write_outputs(md: str, report: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat().replace(":", "-").replace(".", "-")
    (LOG_DIR / f"brief-{stamp}.md").write_text(md, encoding="utf-8")
    (LOG_DIR / f"run-{stamp}.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
