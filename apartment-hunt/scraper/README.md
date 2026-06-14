# Apartment Hunt — daily brief (Apify + email)

A once-a-day (10am) brief of **new** rental listings near UTMB Galveston:
top 5 from **Facebook Marketplace** + 2 from each apartment site, excluding
listings you've already saved. Apify does the scraping (their cloud + proxies);
this runs on your PC and emails you the brief. **Pure Python standard library —
nothing to pip install.**

## One-time setup

1. **Install Python 3.11+** (python.org). No packages needed.

2. **Apify** — make a free account and copy your **API token** (Settings →
   Integrations). Facebook is already wired to the official
   **`apify/facebook-marketplace-scraper`** actor (~$5 / 1,000 listings, free
   $5/mo credits) with `includeListingDetails: true` so descriptions come
   through. For the apartment sites, either feed them via your own connectors
   (drop JSON in `data/incoming/<site>.json`) or add Apify actors and set their
   IDs in `config.json`.

   Test the Facebook scrape on its own anytime:
   ```
   python src/scrape_facebook.py      # calls Apify, prints a summary of each listing
   ```

3. **Config:**
   ```
   copy daily.config.example.json config.json
   ```
   Edit `config.json`:
   - `apifyToken` → your Apify token
   - each source's `apify.actorId` → the actor IDs you added (and tweak `input`
     to match what that actor expects — paste a sample of its output to me and
     I'll lock the field mapping)
   - `email.enabled` → `true`, `email.gmailUser` → your Gmail, `email.appPassword`
     → a Gmail **App Password** (Google Account → Security → 2-Step Verification
     → App passwords). `email.to` is already your address.

4. **Seed what you've already saved** so the brief only shows new listings:
   ```
   python src/seed_saved.py
   ```
   (`saved-fb-ids.txt` already holds the 19 listings from your saved PDF.)

5. **Test it:**
   ```
   python src/daily.py
   ```
   Writes a brief to `logs/` and emails it if email is enabled.

6. **Schedule 10am daily:**
   ```
   ./schedule-daily.ps1
   ```

## Files
- `src/daily.py` — the orchestrator (fetch → filter → dedup → brief → email).
- `src/scrape_facebook.py` — call the Apify FB Marketplace actor + preview each listing.
- `src/filtering.py` — budget rule, negation-aware keyword matching, dedup state.
- `src/sources.py` — per-site field mapping (confirm vs your actors).
- `src/fetch_apify.py` — runs an Apify actor (stdlib `urllib`).
- `src/send_email.py` — Gmail send (stdlib `smtplib`).
- `src/seed_saved.py` — seed already-saved listings into the dedup state.
- `daily.config.example.json` — config template.
- `sample-apify-results.json`, `sample-apartments.json` — fixtures you can run
  against offline: `python src/daily.py` after pointing a source at a `"file"`.

## Notes / honesty
- Field mappings in `sources.py` use common actor field names; **confirm against
  your actual actors' output** (send me a sample and I'll finalize).
- Budget rule: ≤$1200 if utilities included, ≤$1000 if explicitly excluded, and
  the generous cap if utilities aren't mentioned (so unknowns aren't dropped).
- Ranking is currently cheapest-first; commute-to-UTMB / "bougie" scoring is a
  later enrichment step.
- Secrets (`config.json`, `auth/`, `data/`, `logs/`) are gitignored.
