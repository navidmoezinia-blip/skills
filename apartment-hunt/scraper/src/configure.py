"""Interactive config writer. Prompts for the important values and fills sane
defaults (including the credential + budget fields) for everything else."""

import json
from pathlib import Path


CONFIG_PATH = Path("config.json")
EXAMPLE_CONFIG_PATH = Path("config.example.json")
PLACEHOLDER_URL = "https://www.facebook.com/marketplace/your_saved_search_url_here"
PLACEHOLDER_COLLECTION = "My Existing Collection"


def main() -> None:
    config = load_config()

    print("Facebook Marketplace scraper setup")
    print("Press Enter to keep the current value shown in brackets.")
    print()

    config["savedSearchUrl"] = prompt_required(
        "Saved search URL",
        clean_default(config.get("savedSearchUrl"), PLACEHOLDER_URL),
        validate_saved_search_url,
    )
    config["collectionName"] = prompt_required(
        "Existing collection name",
        clean_default(config.get("collectionName"), PLACEHOLDER_COLLECTION),
        lambda value: bool(value.strip()),
    )

    config["fbEmail"] = input(format_prompt("Facebook email/phone", config.get("fbEmail", ""))).strip() or config.get("fbEmail", "")
    config["fbPassword"] = input(format_prompt("Facebook password (stored locally only)", config.get("fbPassword", ""))).strip() or config.get("fbPassword", "")

    config["maxListings"] = prompt_int("Max listings per run", config.get("maxListings", 30), minimum=1)
    config["maxScrolls"] = prompt_int("Max scrolls while finding listings", config.get("maxScrolls", 8), minimum=1)
    config["briefMaxListings"] = prompt_int("Max listings in brief", config.get("briefMaxListings", 5), minimum=1)
    config["freshListingsOnly"] = prompt_bool("Filter Facebook search to recent listings", config.get("freshListingsOnly", True))
    config["freshListingHours"] = prompt_int("Recent listing window in hours", config.get("freshListingHours", 24), minimum=1)
    config["onlyNewListings"] = prompt_bool("Only process new listings", config.get("onlyNewListings", True))
    config["headless"] = prompt_bool("Run headless (yes for scheduled runs)", config.get("headless", True))

    config.setdefault("profileDir", "auth/browser-profile")
    config.setdefault("loginWaitSeconds", 180)
    config.setdefault("stateFile", "data/seen-listings.json")
    config.setdefault(
        "criteria",
        {"includeAny": [], "includeAll": ["in unit"], "excludeAny": ["carpet"], "minPrice": None, "maxPrice": 1200},
    )
    config.setdefault(
        "budget",
        {
            "withUtilitiesMax": 1200,
            "withoutUtilitiesMax": 1000,
            "utilitiesIncludedPhrases": [
                "utilities included", "utils included", "all bills paid",
                "includes utilities", "water included", "electric included",
            ],
        },
    )
    config.setdefault(
        "selectors",
        {
            "listingLinks": "a[href*='/marketplace/item/']",
            "saveButtonNames": ["Save", "Save listing"],
            "savedButtonNames": ["Saved", "Saved listing"],
            "doneButtonNames": ["Done", "Close"],
        },
    )

    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print()
    print(f"Wrote {CONFIG_PATH} (keep this file local — it is gitignored).")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))


def prompt_required(label: str, default: str, validator) -> str:
    while True:
        value = input(format_prompt(label, default)).strip() or default
        if validator(value):
            return value
        print(f"Invalid {label.lower()}.")


def prompt_int(label: str, default: int, minimum: int) -> int:
    while True:
        value = input(format_prompt(label, str(default))).strip()
        if not value:
            return int(default)
        try:
            parsed = int(value)
        except ValueError:
            print("Enter a whole number.")
            continue
        if parsed >= minimum:
            return parsed
        print(f"Enter {minimum} or higher.")


def prompt_bool(label: str, default: bool) -> bool:
    default_text = "yes" if default else "no"
    while True:
        value = input(format_prompt(f"{label} yes/no", default_text)).strip().lower()
        if not value:
            return bool(default)
        if value in {"y", "yes", "true", "1"}:
            return True
        if value in {"n", "no", "false", "0"}:
            return False
        print("Enter yes or no.")


def format_prompt(label: str, default: str) -> str:
    return f"{label} [{default}]: " if default else f"{label}: "


def clean_default(value, placeholder: str) -> str:
    value = "" if value is None else str(value)
    return "" if value == placeholder else value


def validate_saved_search_url(value: str) -> bool:
    return value.startswith("https://www.facebook.com/marketplace/") and "your_saved_search_url_here" not in value


if __name__ == "__main__":
    main()
