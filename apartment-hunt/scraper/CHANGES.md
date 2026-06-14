# Hardened scraper — what changed & how to run

This is the reviewed/fixed version of the Codex scraper. Drop these files over
your local project (`src/run.py`, `src/setup_login.py`, `src/check_login.py`,
`src/configure.py`, `config.example.json`, `.gitignore`).

## Fixes applied (maps to the review)

1. **Listing-scoped matching.** Title/price/description now come from the
   listing's `og:` meta tags and the `[role=main]` column instead of the whole
   page body, so the "More listings like this" sidebar no longer pollutes
   matches or steals the price. (`extract_listing`)
2. **Negation-aware, word-boundary keywords.** `excludeAny: ["carpet"]` no
   longer rejects a *"no carpet"* listing; terms match on word boundaries.
   (`contains_word`)
3. **Conditional budget rule.** New `budget` block enforces *≤ withUtilitiesMax
   if utilities look included, else ≤ withoutUtilitiesMax* — i.e. your
   "≤$1200 with utilities / ≤$1000 without". Unknown price isn't dropped.
   (`budget_check`)
4. **Verified saves + no re-Save loop.** After picking the collection it checks
   the button flipped to **Saved** before reporting `added`. Every processed
   listing is marked *seen* (even if the add failed) so it never re-clicks Save
   and toggles a listing back off. Items it couldn't auto-add are listed in the
   brief under "Matched but could not auto-add". (`add_to_collection`, main loop)
5. **Honest freshness.** `freshListingHours` now maps to FB's real day buckets
   (1/7/30) instead of silently disabling the filter for >24h, and the final
   search URL is printed so you can confirm the params took. Note FB only
   supports day-granularity recency, and it's still best-effort (no per-listing
   timestamp guarantee). (`build_search_url`)
6. **Auto-login + working selector.** Logs in from `fbEmail`/`fbPassword`
   (config) or `FB_EMAIL`/`FB_PASSWORD` (env), submitting via **Enter** (FB
   removed `button[name=login]`). Headless runs that hit a 2FA/CAPTCHA fail
   cleanly with a "needs manual login" brief instead of hanging.
7. **One profile, gitignored secrets.** Scraper, login, and check all use
   `auth/browser-profile`. `.gitignore` excludes `auth/`, `config.json`,
   `data/`, `logs/`, `.env`.
8. **Unattended-safe.** Headless by default, a `data/.run.lock` prevents
   overlapping runs, state saves after every listing (crash-safe), session
   walls (`/login`, `/checkpoint`, `two_step_verification`) are detected, and a
   realistic UA + `--disable-blink-features=AutomationControlled` are set.

## ⚠️ About login on this account

This throwaway account has **2FA on**, and FB shows a **CAPTCHA** to automated
logins (confirmed live). So a pure "log in fresh every run" can't run unattended
— it gets stuck at the code/CAPTCHA. The flow that works:

- **First time:** `python src/setup_login.py` → a visible browser opens,
  auto-fills your credentials, you clear the 2FA/CAPTCHA **once**. FB's "remember
  this browser" is stored in the profile.
- **Daily:** `python src/run.py` runs headless and reuses that session.

To make it *fully* unattended (no one-time step), **turn off 2FA** on the
throwaway account in Facebook settings; then auto-login works on its own (still
the occasional CAPTCHA).

## Setup

```powershell
pip install playwright
python -m playwright install chromium

copy config.example.json config.json   # then edit config.json:
#   savedSearchUrl  -> your real Marketplace saved-search URL (from the address bar)
#   collectionName  -> your existing FB collection's exact name
#   fbEmail/fbPassword -> the throwaway account (stays local; gitignored)
#   tune criteria/budget to taste

python src/setup_login.py   # one-time: sign in, clear 2FA/CAPTCHA
python src/run.py           # the daily run
```

## How to sanity-check it works

- Run with `"headless": false` once and watch it open listings and click Save.
- Open `logs/brief-*.md` — confirm titles look like real listing titles (not
  nav text) and prices are the listing's own. If a title looks like boilerplate,
  the `og:` fallback needs tuning for the current FB markup — tell me and I'll
  adjust the selectors.
- Check your Facebook collection actually contains the "ADDED" items.

## Tuning notes (keyword limits)

- **W/D detection is keyword-based.** `includeAny` lists common phrasings
  ("in unit", "in-unit", "washer and dryer", "washer/dryer", ...). A match means
  at least one appears — it can still miss oddly-worded posts, so eyeball the
  brief and add phrasings as needed.
- **`excludeAny: ["carpet"]` is a *hard* exclude** (your "no carpet" is a
  preference). "No carpet"/"without carpet" correctly pass; a listing that just
  mentions "carpet" is dropped. If that's too aggressive, remove "carpet" from
  `excludeAny`.

> I can't run this against Facebook from my side (datacenter IP → CAPTCHA), so
> these files are reviewed and logic-tested but not live-tested. Your local run
> is the real test — paste any errors or a `brief-*.md`/`run-*.json` back and
> I'll iterate.
