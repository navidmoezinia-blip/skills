"""One-time (or as-needed) headed login.

Opens a visible browser using the SAME persistent profile the scraper uses,
pre-fills your credentials if they're configured, and waits for you to clear
any 2FA / CAPTCHA. Once Facebook's "remember this browser" sticks, the daily
headless run reuses the session without re-prompting.

The password is never stored by this script beyond filling the form; it is read
from config.json (fbEmail/fbPassword) or the FB_EMAIL/FB_PASSWORD env vars.
"""

import json
import os
from pathlib import Path
from time import monotonic, sleep

from playwright.sync_api import sync_playwright


CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "config.json"))
DEFAULT_PROFILE_DIR = Path("auth/browser-profile")


def main() -> None:
    config = load_config()
    profile_dir = Path(config.get("profileDir") or DEFAULT_PROFILE_DIR)
    profile_dir.mkdir(parents=True, exist_ok=True)

    email = config.get("fbEmail") or os.environ.get("FB_EMAIL")
    password = config.get("fbPassword") or os.environ.get("FB_PASSWORD")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        print("Opening Facebook. This uses a dedicated browser profile, separate")
        print("from your normal Chrome. Log in / clear any 2FA or CAPTCHA, then wait.")

        page.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=60_000)
        if email and password and page.locator("input[name='pass']").count() > 0:
            try:
                page.locator("input[name='email']").fill(email)
                page.locator("input[name='pass']").fill(password)
                page.locator("input[name='pass']").press("Enter")  # FB removed button[name=login]
                print("Submitted credentials; complete any 2FA/CAPTCHA in the window.")
            except Exception as exc:  # noqa: BLE001
                print(f"Auto-fill failed ({exc}); just log in manually in the window.")

        wait_for_logged_in_cookie(context)
        context.close()

    print(f"Saved login session in {profile_dir}")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def wait_for_logged_in_cookie(context, minutes: int = 10) -> None:
    deadline = monotonic() + (minutes * 60)
    while monotonic() < deadline:
        if any(c.get("name") == "c_user" for c in context.cookies("https://www.facebook.com")):
            print("Login detected.")
            return
        sleep(1)
    raise TimeoutError(
        f"Timed out after {minutes} min waiting for the Facebook login cookie. "
        "Log in fully before the timeout."
    )


if __name__ == "__main__":
    main()
