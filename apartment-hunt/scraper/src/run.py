"""Facebook Marketplace apartment scraper (hardened).

Runs daily: opens a saved-search, collects new listing links, checks each
listing against criteria, optionally adds matches to an existing collection,
and writes a run report + a brief (max N listings).

Key behaviours vs. the original:
- Matching/price/title come from the listing's own content (og: meta + the
  main column), NOT the whole page body, so sidebar "more listings" no longer
  pollutes results.
- Word-boundary + negation-aware keyword matching ("no carpet" is not a
  "carpet" hit).
- Optional conditional budget rule (<= withUtilitiesMax if utilities are
  included, else <= withoutUtilitiesMax).
- Save -> collection is verified (button flips to "Saved") before reporting
  "added"; every processed listing is marked seen so we never re-click Save
  on the same item; "matched but couldn't add" is surfaced for manual handling.
- Auto-login from config/env credentials, with a persistent profile so FB's
  "remember this browser" suppresses repeated 2FA. Headless runs fail cleanly
  with a "needs manual login" brief instead of hanging on a challenge.
- Lockfile prevents overlapping runs; state is saved incrementally; session
  expiry (login / checkpoint / 2FA) is detected and reported, not crashed on.
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "config.json"))
LOG_DIR = Path("logs")
DEFAULT_STATE_PATH = Path("data/seen-listings.json")
DEFAULT_PROFILE_DIR = Path("auth/browser-profile")
LOCK_PATH = Path("data/.run.lock")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
MARKETPLACE_HOME = "https://www.facebook.com/marketplace/"


class SessionError(RuntimeError):
    """Raised when Facebook is not authenticated (login / checkpoint / 2FA)."""


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    validate_config(config)

    state_path = Path(config.get("stateFile") or DEFAULT_STATE_PATH)
    profile_dir = Path(config.get("profileDir") or DEFAULT_PROFILE_DIR)
    headless = resolve_headless(config)
    state = load_state(state_path)
    report = new_report()

    acquire_lock(LOCK_PATH)
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(profile_dir),
                headless=headless,
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 2200},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()
            try:
                ensure_logged_in(context, page, config, headless)

                search_url = build_search_url(config)
                print(f"Search URL: {search_url}")
                page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
                wait_for_network_quiet(page)
                ensure_session(page)

                selectors = config.get("selectors", {})
                links = collect_listing_links(
                    page,
                    selectors.get("listingLinks", "a[href*='/marketplace/item/']"),
                    int(config.get("maxListings", 30)),
                    int(config.get("maxScrolls", 8)),
                )
                report["scanned"] = len(links)
                print(f"Found {len(links)} listing links.")

                brief_limit = int(config.get("briefMaxListings", 5))
                for url in links:
                    listing_key = listing_id_from_url(url) or url
                    if config.get("onlyNewListings", True) and listing_key in state["seen"]:
                        report["alreadySeen"] += 1
                        continue

                    report["new"] += 1
                    report["checked"] += 1
                    try:
                        result = process_listing(page, url, config)
                    except SessionError:
                        raise  # abort the whole run; handled below
                    except Exception as exc:  # noqa: BLE001 - per-listing isolation
                        report["errors"].append({"url": url, "error": str(exc)})
                        print(f"ERROR {url}: {exc}")
                        continue  # do NOT mark seen on a hard error -> retry next run

                    if result["matched"]:
                        report["matched"] += 1
                        add_to_brief(report, result, brief_limit)
                    if result["added"]:
                        report["added"] += 1
                    if result["matched"] and not result["added"]:
                        report["needsManualAdd"].append(
                            {
                                "url": url,
                                "title": result["listing"]["title"],
                                "reason": result.get("reason"),
                            }
                        )
                    if not result["matched"] and result.get("reason"):
                        report["skipped"].append({"url": url, "reason": result["reason"]})

                    status = (
                        "ADDED"
                        if result["added"]
                        else "NEEDS_ADD"
                        if result["matched"]
                        else "SKIP"
                    )
                    print(f"{status} {url} {result.get('reason', '') or ''}".rstrip())

                    # Always mark seen once processed (matched or not) so we never
                    # re-click Save on the same listing and toggle it off.
                    remember_seen(state, listing_key, url, status, result.get("reason"))
                    save_state(state_path, state)  # incremental: survive a crash
            except SessionError as se:
                report["sessionError"] = str(se)
                print(f"SESSION ERROR: {se}")
            finally:
                context.close()
    finally:
        release_lock(LOCK_PATH)
        save_state(state_path, state)
        write_outputs(report)


# --------------------------------------------------------------------------- #
# Login / session
# --------------------------------------------------------------------------- #
def ensure_logged_in(context, page: Page, config: dict, headless: bool) -> None:
    """Make sure we have a live FB session, auto-logging in if needed."""
    page.goto(MARKETPLACE_HOME, wait_until="domcontentloaded", timeout=60_000)
    wait_for_network_quiet(page)
    if has_login_cookie(context):
        return

    email = config.get("fbEmail") or os.environ.get("FB_EMAIL")
    password = config.get("fbPassword") or os.environ.get("FB_PASSWORD")
    if not email or not password:
        raise SessionError(
            "Not logged in and no credentials configured. Run src/setup_login.py "
            "once (headed) to sign in, or set fbEmail/fbPassword in config.json."
        )

    print("Not logged in; attempting auto-login.")
    page.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=60_000)
    submit_login_form(page, email, password)

    wait_seconds = int(config.get("loginWaitSeconds", 180))
    deadline = monotonic() + wait_seconds
    warned = False
    while monotonic() < deadline:
        if has_login_cookie(context):
            print("Login succeeded.")
            return
        if challenge_present(page):
            if headless:
                raise SessionError(
                    "Facebook is asking for 2FA/CAPTCHA and this run is headless. "
                    "Run src/setup_login.py once (a visible window) to clear it; the "
                    "profile then remembers this browser."
                )
            if not warned:
                print(
                    ">> Facebook needs a 2FA code / CAPTCHA cleared in the open "
                    "browser window. Do it now; I'll keep waiting..."
                )
                warned = True
        sleep(2)

    raise SessionError(f"Timed out after {wait_seconds}s waiting for Facebook login.")


def submit_login_form(page: Page, email: str, password: str) -> None:
    # FB's login button is no longer button[name='login']; submit via Enter.
    try:
        page.locator("input[name='email']").fill(email, timeout=15_000)
        page.locator("input[name='pass']").fill(password, timeout=15_000)
        page.locator("input[name='pass']").press("Enter")
    except PlaywrightTimeoutError as exc:
        raise SessionError(f"Could not find/fill the login form: {exc}") from exc


def challenge_present(page: Page) -> bool:
    url = page.url
    if "two_step_verification" in url or "/checkpoint" in url or "two_factor" in url:
        return True
    try:
        recaptcha = page.locator(
            "iframe[src*='recaptcha'], iframe[title*='recaptcha']"
        ).count()
        if recaptcha > 0:
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def has_login_cookie(context) -> bool:
    return any(
        cookie.get("name") == "c_user"
        for cookie in context.cookies("https://www.facebook.com")
    )


def ensure_session(page: Page) -> None:
    """Raise SessionError if the current page is a login/checkpoint/2FA wall."""
    url = page.url
    if "/login" in url or "/checkpoint" in url or "two_step_verification" in url:
        raise SessionError(f"Facebook redirected to an auth wall: {url}")
    if not has_login_cookie(page.context):
        raise SessionError("No Facebook login cookie (c_user) present.")


# --------------------------------------------------------------------------- #
# Search URL + link collection
# --------------------------------------------------------------------------- #
def build_search_url(config: dict) -> str:
    url = str(config["savedSearchUrl"])
    if not config.get("freshListingsOnly", True):
        return url

    hours = int(config.get("freshListingHours", 24))
    # FB exposes coarse day buckets, not hours. Map to the nearest supported one
    # instead of silently dropping the filter for hours > 24.
    if hours <= 24:
        days = "1"
    elif hours <= 7 * 24:
        days = "7"
    else:
        days = "30"

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["daysSinceListed"] = days
    query["sortBy"] = "creation_time_descend"
    rebuilt = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    if days != "1":
        print(
            f"Note: freshListingHours={hours} -> daysSinceListed={days} "
            "(FB only supports day-granularity recency)."
        )
    return rebuilt


def collect_listing_links(
    page: Page, selector: str, max_listings: int, max_scrolls: int
) -> list[str]:
    seen: dict[str, None] = {}

    for _ in range(max_scrolls):
        if len(seen) >= max_listings:
            break

        hrefs = page.locator(selector).evaluate_all(
            """
            anchors => anchors
              .map(anchor => anchor.href)
              .filter(href => href && href.includes('/marketplace/item/'))
            """
        )
        for href in hrefs:
            canonical = href.split("?")[0]
            seen.setdefault(canonical, None)
            if len(seen) >= max_listings:
                break

        # JS scroll is reliable; mouse.wheel at (0,0) often doesn't move the feed.
        page.evaluate("window.scrollBy(0, Math.round(window.innerHeight * 0.9));")
        page.wait_for_timeout(1200)

    return list(seen.keys())[:max_listings]


# --------------------------------------------------------------------------- #
# Per-listing processing
# --------------------------------------------------------------------------- #
def process_listing(page: Page, url: str, config: dict) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    wait_for_network_quiet(page)
    ensure_session(page)

    listing = extract_listing(page, url)
    match_text = f"{listing['title']} {listing['description']}"

    crit = matches_criteria(match_text, listing["price"], config.get("criteria", {}))
    if not crit["ok"]:
        return _result(False, False, False, crit["reason"], listing)

    budget_ok, budget_reason = budget_check(match_text, listing["price"], config.get("budget"))
    if not budget_ok:
        return _result(False, False, False, budget_reason, listing)

    add = add_to_collection(page, config)
    return _result(True, add["added"], add["saved"], add.get("reason"), listing)


def _result(matched, added, saved, reason, listing) -> dict:
    return {
        "matched": matched,
        "added": added,
        "saved": saved,
        "reason": reason,
        "listing": listing,
    }


def extract_listing(page: Page, url: str) -> dict:
    """Pull title/price/description/location from the listing itself."""
    title = meta_content(page, "og:title")
    description = meta_content(page, "og:description")

    # Fall back to the main column (excludes the global nav header), never the
    # whole body which includes the "more listings" sidebar.
    main_text = scoped_main_text(page)
    if not title:
        title = (page.title() or "Marketplace listing").split(" | ")[0]
    if not description:
        description = main_text[:1200]

    price = (
        first_price(title)
        or first_price(description)
        or first_price(main_text[:1500])
    )
    location = ""
    loc_match = re.search(r"[A-Z][a-zA-Z .'-]+,\s?[A-Z]{2}\b", main_text[:1500])
    if loc_match:
        location = loc_match.group(0)

    return {
        "title": normalize(title)[:140] or "Marketplace listing",
        "price": price,
        "location": normalize(location)[:120],
        "description": normalize(description),
        "url": url,
    }


def meta_content(page: Page, prop: str) -> str:
    try:
        loc = page.locator(f"meta[property='{prop}']").first
        if loc.count() > 0:
            return loc.get_attribute("content", timeout=5_000) or ""
    except Exception:  # noqa: BLE001
        return ""
    return ""


def scoped_main_text(page: Page) -> str:
    try:
        main = page.locator("[role='main']").first
        if main.count() > 0:
            return normalize(main.inner_text(timeout=20_000))
    except Exception:  # noqa: BLE001
        pass
    try:
        return normalize(page.locator("body").inner_text(timeout=20_000))
    except Exception:  # noqa: BLE001
        return ""


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
def matches_criteria(text: str, price: int | None, criteria: dict) -> dict:
    lower = text.lower()

    for word in criteria.get("excludeAny", []):
        if contains_word(lower, str(word), allow_negated=False):
            return {"ok": False, "reason": f'excluded by "{word}"'}

    for word in criteria.get("includeAll", []):
        if not contains_word(lower, str(word)):
            return {"ok": False, "reason": f'missing required "{word}"'}

    include_any = criteria.get("includeAny", [])
    if include_any and not any(contains_word(lower, str(w)) for w in include_any):
        return {"ok": False, "reason": "missing includeAny term"}

    min_price = criteria.get("minPrice")
    max_price = criteria.get("maxPrice")
    if min_price is not None and price is not None and price < min_price:
        return {"ok": False, "reason": f"price {price} below min {min_price}"}
    if max_price is not None and price is not None and price > max_price:
        return {"ok": False, "reason": f"price {price} above max {max_price}"}

    return {"ok": True, "reason": None}


def contains_word(text: str, term: str, allow_negated: bool = True) -> bool:
    """Word-boundary match. With allow_negated=False, an occurrence immediately
    preceded by no/without/not does NOT count (so "no carpet" != "carpet")."""
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


def budget_check(text: str, price: int | None, budget: dict | None) -> tuple[bool, str | None]:
    """Conditional rule: <= withUtilitiesMax if utilities look included,
    else <= withoutUtilitiesMax. Unknown price is not dropped."""
    if not budget or price is None:
        return True, None
    phrases = [
        p.lower()
        for p in budget.get(
            "utilitiesIncludedPhrases",
            ["utilities included", "utils included", "all bills paid",
             "water included", "includes utilities", "electric included"],
        )
    ]
    utilities_included = any(p in text.lower() for p in phrases)
    cap = budget.get("withUtilitiesMax", 1200) if utilities_included else budget.get("withoutUtilitiesMax", 1000)
    if cap is not None and price > cap:
        tag = "utils incl" if utilities_included else "utils not stated/excl"
        return False, f"price ${price} over ${cap} ({tag})"
    return True, None


# --------------------------------------------------------------------------- #
# Save to collection (verified)
# --------------------------------------------------------------------------- #
def add_to_collection(page: Page, config: dict) -> dict:
    selectors = config.get("selectors", {})
    save_names = selectors.get("saveButtonNames", ["Save", "Save listing"])
    saved_names = selectors.get("savedButtonNames", ["Saved", "Saved listing"])
    collection_name = config["collectionName"]

    if button_visible(page, saved_names, 1200):
        # Already saved on a prior run; don't re-click (would unsave).
        return {"added": False, "saved": True, "reason": "already saved previously"}

    clicked_save = False
    for name in save_names:
        button = page.get_by_role("button", name=exact_ci(name)).first
        if is_visible(button, 3000):
            button.click()
            page.wait_for_timeout(1200)
            clicked_save = True
            break
    if not clicked_save:
        return {"added": False, "saved": False, "reason": "Save control not found"}

    chosen = False
    for locator in collection_candidates(page, collection_name):
        if is_visible(locator, 2500):
            locator.click()
            page.wait_for_timeout(800)
            chosen = True
            break
    if not chosen:
        return {
            "added": False,
            "saved": True,
            "reason": f'collection "{collection_name}" not found in Save dialog',
        }

    click_first_visible_button(page, selectors.get("doneButtonNames", ["Done", "Close"]))
    page.wait_for_timeout(800)

    verified = button_visible(page, saved_names, 2000)
    return {
        "added": bool(verified),
        "saved": True,
        "reason": None if verified else "clicked collection but could not verify 'Saved' state",
    }


def collection_candidates(page: Page, name: str):
    rx = re.compile(re.escape(name), re.I)
    return [
        page.get_by_role("menuitemcheckbox", name=rx).first,
        page.get_by_role("checkbox", name=rx).first,
        page.get_by_role("menuitem", name=rx).first,
        page.get_by_role("option", name=rx).first,
        page.get_by_text(name, exact=True).first,
    ]


def click_first_visible_button(page: Page, names: list[str]) -> bool:
    for name in names:
        button = page.get_by_role("button", name=exact_ci(name)).first
        if is_visible(button, 1500):
            button.click()
            return True
    return False


def button_visible(page: Page, names: list[str], timeout: int) -> bool:
    for name in names:
        button = page.get_by_role("button", name=exact_ci(name)).first
        if is_visible(button, timeout):
            return True
    return False


def exact_ci(name: str) -> re.Pattern:
    return re.compile(rf"^{re.escape(name)}$", re.I)


# --------------------------------------------------------------------------- #
# Report / brief
# --------------------------------------------------------------------------- #
def new_report() -> dict:
    return {
        "scanned": 0,
        "new": 0,
        "alreadySeen": 0,
        "checked": 0,
        "matched": 0,
        "added": 0,
        "skipped": [],
        "needsManualAdd": [],
        "errors": [],
        "topListings": [],
        "sessionError": None,
    }


def add_to_brief(report: dict, result: dict, limit: int) -> None:
    if len(report["topListings"]) >= max(0, limit):
        return
    listing = result.get("listing")
    if listing:
        report["topListings"].append({**listing, "added": result["added"]})


def render_brief(report: dict) -> str:
    lines = ["# Apartment Listing Brief", ""]

    if report.get("sessionError"):
        lines += [
            "> ⚠️ **SESSION EXPIRED — no listings scraped.**",
            f"> {report['sessionError']}",
            "> Run `python src/setup_login.py` (visible window) to sign in again.",
            "",
        ]

    lines += [
        f"- Scanned: {report['scanned']}",
        f"- New checked: {report['checked']}",
        f"- Matched: {report['matched']}",
        f"- Added to collection: {report['added']}",
        f"- Matched but not added: {len(report['needsManualAdd'])}",
        f"- Errors: {len(report['errors'])}",
        "",
        "## Top Listings",
        "",
    ]

    if not report["topListings"]:
        lines.append("No matching new listings found.")
    else:
        for index, listing in enumerate(report["topListings"], start=1):
            price = f"${listing['price']:,}" if listing.get("price") is not None else "Price not found"
            location = f" — {listing['location']}" if listing.get("location") else ""
            flag = "" if listing.get("added") else "  _(not added — save manually)_"
            lines += [
                f"{index}. [{listing['title']}]({listing['url']})",
                f"   {price}{location}{flag}",
                "",
            ]

    if report["needsManualAdd"]:
        lines += ["## Matched but could not auto-add", ""]
        for item in report["needsManualAdd"]:
            lines.append(f"- [{item['title']}]({item['url']}) — {item.get('reason') or 'unknown reason'}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_outputs(report: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat().replace(":", "-").replace(".", "-")
    (LOG_DIR / f"run-{stamp}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (LOG_DIR / f"brief-{stamp}.md").write_text(render_brief(report), encoding="utf-8")


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
def load_state(path: Path) -> dict:
    if not path.exists():
        return {"seen": {}}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"seen": {str(key): {"url": str(key)} for key in loaded}}
    if not isinstance(loaded, dict):
        return {"seen": {}}
    loaded.setdefault("seen", {})
    return loaded


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)  # atomic on the same filesystem


def remember_seen(state: dict, listing_key: str, url: str, status: str, reason: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    prior = state["seen"].get(listing_key, {})
    state["seen"][listing_key] = {
        "url": url,
        "firstSeenAt": prior.get("firstSeenAt", now),
        "lastSeenAt": now,
        "lastStatus": status,
        "lastReason": reason,
    }


def listing_id_from_url(url: str) -> str | None:
    match = re.search(r"/marketplace/item/([^/?#]+)", url)
    return match.group(1) if match else None


# --------------------------------------------------------------------------- #
# Misc helpers
# --------------------------------------------------------------------------- #
def validate_config(config: dict) -> None:
    saved_search_url = str(config.get("savedSearchUrl", ""))
    collection_name = str(config.get("collectionName", ""))
    if "your_saved_search_url_here" in saved_search_url or not saved_search_url.startswith(
        "https://www.facebook.com/marketplace/"
    ):
        raise RuntimeError(
            "Set savedSearchUrl in config.json to your real Facebook Marketplace "
            "saved-search URL (copy it from the browser address bar after applying filters)."
        )
    if collection_name == "My Existing Collection" or not collection_name.strip():
        raise RuntimeError("Set collectionName in config.json to your existing Facebook collection name.")


def resolve_headless(config: dict) -> bool:
    value = config.get("headless", True)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "no", "off"}
    return bool(value)


def acquire_lock(lock_path: Path) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        age = time.time() - lock_path.stat().st_mtime
        if age < 2 * 3600:
            raise RuntimeError(
                f"Another run looks active (lock {lock_path}, age {int(age)}s). "
                "Delete it if you're sure no run is in progress."
            )
        print(f"Removing stale lock ({int(age)}s old).")
    lock_path.write_text(str(os.getpid()), encoding="utf-8")


def release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def wait_for_network_quiet(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=30_000)
    except PlaywrightTimeoutError:
        pass


def is_visible(locator, timeout: int) -> bool:
    try:
        return locator.is_visible(timeout=timeout)
    except PlaywrightTimeoutError:
        return False
    except Exception:  # noqa: BLE001 - locator may resolve to 0 elements
        return False


def first_price(text: str) -> int | None:
    match = re.search(r"\$\s?([0-9][0-9,]*)", text or "")
    return int(match.group(1).replace(",", "")) if match else None


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


if __name__ == "__main__":
    main()
