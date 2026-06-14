"""Quick check that the persistent profile still has a live Facebook session."""

import json
import os
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright


CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "config.json"))
DEFAULT_PROFILE_DIR = Path("auth/browser-profile")


def profile_dir() -> Path:
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return Path(config.get("profileDir") or DEFAULT_PROFILE_DIR)
    return DEFAULT_PROFILE_DIR


def main() -> None:
    target = profile_dir()
    if not target.exists():
        raise SystemExit(f"No browser profile at {target}. Run src/setup_login.py first.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(target), headless=True)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(
                "https://www.facebook.com/marketplace/",
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except PlaywrightTimeoutError:
                pass

            url = page.url
            logged_in = any(
                c.get("name") == "c_user" for c in context.cookies("https://www.facebook.com")
            )
            walled = any(s in url for s in ("/login", "/checkpoint", "two_step_verification"))
            if logged_in and not walled:
                print(f"Facebook login check passed for {target}.")
                return
            raise SystemExit(
                "Facebook login check FAILED "
                f"(logged_in={logged_in}, url={url}). Run src/setup_login.py and log in fully."
            )
        finally:
            context.close()


if __name__ == "__main__":
    main()
