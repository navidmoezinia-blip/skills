# Apartment Hunt Directory — Build Brief

**Audience:** This is a spec to hand to a coding agent (Codex/Abacus) to implement.
**Author of brief:** Claude (info-gathering + spec). **Implementer:** Codex.
**Last updated:** 2026-06-14

---

## 1. Goal

A self-updating "apartment hunt" directory that scrapes **Facebook Marketplace**
for rentals matching a fixed profile, enriches each listing with derived fields
(upfront cost, commute, a "bougie" score, etc.), and **emails a digest twice a
day**. It runs unattended on the user's own machine.

> **Design principle:** This is a *scheduled program*, not a recurring AI chat
> task. Build it once; a cron job runs it twice daily with **no chat-tool usage**.
> The only AI in the loop at runtime is a single cheap LLM API call per run that
> computes the subjective/derived fields. This keeps it off the user's
> Claude/Codex/Abacus interactive limits.

---

## 2. The hunter's profile (search criteria)

| Attribute | Value |
|---|---|
| Who | PGY1 Family Medicine resident at **UTMB (Galveston, TX)** |
| Commute anchor | UTMB main campus, **301 University Blvd, Galveston, TX 77555** (confirmed) |
| Budget | **≤ $1,200/mo if utilities included**, OR **≤ $1,000/mo if utilities not included** |
| Must-have | **In-unit washer/dryer** (hard filter — exclude listings without it) |
| Strong preference | **No carpet** (hard floors) |
| Size | **Smaller is better; ideal ~500 sqft.** Do not exclude small units; rank them up. |
| Location | **Closer to UTMB = better** |
| Move timeline | Essentials move first, full move before **end of July 2026** — so listings available **now through July** are relevant |

### Hard filters (exclude if violated)
1. No in-unit washer/dryer → exclude.
2. Over budget per the utilities-conditional rule above → exclude.
   - Compute: if listing says utilities included and rent ≤ $1200 → keep. If
     utilities NOT included and rent ≤ $1000 → keep. If utilities status unknown,
     keep but flag `utilities: "unknown"` and apply the ≤$1000 threshold
     conservatively (or surface for manual review rather than hard-dropping).

### Soft preferences (used for ranking, not exclusion)
- Closer to UTMB (shorter commute) → higher rank.
- No carpet → higher rank.
- Closer to ~500 sqft → higher rank (penalize very large units lightly).
- Higher bougie rating → higher rank, but never above budget/commute.

---

## 3. Per-listing fields (what goes in the directory)

### A. Scraped directly (from FB Marketplace)
- `title`
- `price` (monthly rent, numeric)
- `location` / neighborhood (as posted)
- `photo_url` (primary image)
- `listing_url` (direct link)
- `bedrooms`, `bathrooms` (when present)
- `sqft` (when present)
- `pet_policy` (when present)
- `posted_at` / "listed X days ago"
- `description` (raw text — feeds the enrichment step)

### B. Derived by the LLM enrichment pass (per the user's custom asks)
- **`total_upfront_cost`** — best estimate of cash needed to move in:
  first month + deposit + any admin/app fees mentioned. If components are
  missing, estimate and label `"estimated"`; show the breakdown.
- **`specials`** — any promo/concession mentioned (e.g. "1 month free,"
  "$0 deposit," "reduced rent"). Empty if none.
- **`utilities`** — `included` / `not_included` / `partial` / `unknown`, plus a
  short note on which utilities (water/trash/electric/internet) if stated.
- **`commute_to_utmb`** — ease of getting to UTMB Galveston. Categorize as
  `walk` / `bike` / `short_drive (<10 min)` / `drive (10–25 min)` /
  `far (>25 min)`, with the estimated minutes/miles. (See §6 for how to compute.)
- **`bougie_rating`** — integer **/10**, judged from photos + description on a
  fixed rubric (see §5). One-line justification.

### C. Computed by the formatter
- `is_new` — true if this `listing_url` wasn't in the previous run.
- `price_changed` — if seen before at a different price, show old → new.
- `rank_score` — sort key from the soft preferences.

---

## 4. Architecture

```
cron (twice daily)
   └─> run.py
        1. scrape.py      Playwright → logged-in FB Marketplace → raw listings JSON
        2. filter.py      apply hard filters (W/D, budget rule)
        3. enrich.py      ONE LLM API call (batched) → derived fields (§3B, §5)
        4. diff.py        compare vs state/last_run.json → is_new / price_changed
        5. rank.py        compute rank_score, sort
        6. render.py      build HTML email (§7)
        7. send.py        send via Gmail
        8. persist        write state/last_run.json
```

### Runtime decisions (already made with the user)
- **Runs on the user's own machine** (laptop/home server). Chosen because FB
  blocks datacenter IPs; a residential IP + a persistent logged-in browser
  session is the reliable path.
- **Scheduling:** `cron` (Linux) or `launchd` (macOS). Twice daily — suggest
  **~7:30am and ~6:00pm local**. Confirm machine is awake at those times.
- **FB session:** Use Playwright with a **persistent user-data dir** so the
  login/cookies survive between runs. First run is a manual login; after that
  it reuses the session. Do NOT store FB password in code.

### Tech stack (suggested)
- Python 3.11+, `playwright` (chromium), an LLM SDK for the enrichment call,
  Gmail for delivery, `jinja2` for the email template, JSON files for state
  (no DB needed).

---

## 5. Bougie rating rubric (/10)

Make the score reproducible. Score from photos + description:

- **9–10:** Renovated/modern, quartz or granite counters, stainless steel,
  luxury vinyl plank or hardwood, in-unit laundry, designer finishes, pool/gym,
  waterfront or premium building.
- **6–8:** Updated, clean, decent finishes, some amenities, no obvious wear.
- **4–5:** Dated but maintained; basic finishes; functional.
- **1–3:** Worn, old appliances, visible damage, carpet everywhere, dim/dingy.

Add **+1 (cap 10)** if photos show genuinely high-end touches; **−2** if carpet
is the dominant flooring (also conflicts with the no-carpet preference). Always
return a one-line reason so the user can sanity-check.

---

## 6. Commute computation

Anchor: UTMB, 301 University Blvd, Galveston, TX 77555 (confirm exact campus).

Options, simplest first:
1. **Geocode + driving distance via a maps API** (Google Maps Distance Matrix,
   or OpenRouteService free tier) from the listing's neighborhood/address to the
   anchor. Most accurate. Requires an API key.
2. **LLM estimate from neighborhood name** — cheaper, rougher. Galveston is a
   small island; most addresses are within ~15 min of campus, so neighborhood-
   level estimates are usually good enough.

Recommend option 1 if a maps API key is easy; otherwise option 2 is acceptable
given Galveston's small size. Output the category + estimated minutes.

---

## 7. Email digest format

- **Subject:** `🏠 Apartment Hunt — {N} matches ({M} new) — {date} {am/pm}`
- **Top section:** count of total matches, how many are new since last run, any
  price drops.
- **Listing cards**, sorted by `rank_score` (best first). Each card:
  - Photo thumbnail (linked to the listing)
  - Title + **NEW** badge if `is_new`
  - **Rent** + utilities tag (incl. / not incl. / unknown)
  - **Total upfront** (with breakdown on hover/secondary line)
  - Beds/baths/**sqft**, flooring note, **in-unit W/D ✓**
  - **Commute to UTMB:** category + minutes
  - **Bougie:** X/10 — one-line reason
  - **Specials:** if any
  - Direct link button
- **Footer:** timestamp, "next update at …", and a note if the FB session needs
  re-login (so the user knows to fix it).

Keep it skimmable — this is a twice-daily glance, not a report.

---

## 8. Dedup / change tracking

- Key listings by `listing_url` (or a stable FB listing id parsed from it).
- Persist `state/last_run.json` = `{ listing_id: {price, first_seen, last_seen} }`.
- `is_new` = id not in prior state. `price_changed` = price differs from stored.
- Optionally keep an `archive/` of all-ever-seen so a listing that disappears and
  reappears isn't falsely "new."

---

## 9. Defaults + open items

These are resolved with sensible **defaults so Codex can build without blocking**.
The user can override any of them; only the last group truly needs user input.

**Decided / defaulted:**
1. **Commute anchor:** UTMB **main campus, 301 University Blvd, Galveston, TX
   77555** (confirmed by user).
2. **Search radius (default):** Galveston Island first; also include nearby
   mainland (Texas City, La Marque) when commute stays ≲25 min. Rank by commute.
3. **Commute computation (default):** LLM estimate from neighborhood (Galveston
   is small, so this is adequate). Upgrade to a maps API only if a key is given.
4. **Email + send times (default):** to `navidmoezinia@gmail.com`, **7:30am and
   6:00pm America/Chicago (Central)**.
5. **Furnished (default):** no preference — include both.
6. **Lease length (default):** no hard filter; residency is ~3 yr, so note any
   sub-12-month / short-term leases as a minor con but don't exclude.
7. **"Utilities unknown" listings (default):** keep and **surface for manual
   review** (flag `utilities: "unknown"`); do not hard-drop.

**Needs the user (not blocking — can start without):**
- Confirm the Gmail send mechanism on the user's machine (app password / OAuth)
  and that those two send times suit their schedule.
- Whether to add a maps API key for exact commute times.

---

## 10. Build ownership

**Codex builds the whole pipeline** from this brief (user's chosen split).
Claude's contribution is this brief + the live recon (§12) that de-risked the
two failure modes Codex would otherwise hit blind: the mandatory login and the
datacenter-IP CAPTCHA wall. Implement strictly to §12's architecture — a
**one-time headed login on the user's machine** with a **persistent profile**,
then headless twice-daily runs.

The probe scripts in `apartment-hunt/recon/` are a working starting reference:
- `recon.mjs` — proves the logged-out wall + the `ignoreHTTPSErrors` need.
- `login_probe.mjs` / `inspect_login.mjs` — the login flow + current FB
  selectors (`input[name="email"]`, `input[name="pass"]`, submit via Enter).

---

## 11. Known risks / caveats

- **FB actively fights scraping:** login walls, anti-bot challenges, and DOM
  changes that break selectors. Expect occasional breakage; build `scrape.py`
  defensively (retries, clear failure logging, "session expired" detection that
  notes it in the email footer). This is for **personal use** only.
- **No persistent run from a cloud agent** — by design it runs on the user's
  machine so the FB session and residential IP stay stable.
- Derived fields (`bougie`, `total_upfront`) are **estimates** — always label
  them as such so the user verifies before committing money.

---

## 12. Recon findings (2026-06-14)

Live validation was attempted from the (ephemeral, datacenter-IP) build
container. Results:

- **Logged-out Marketplace is fully gated.** `/marketplace/galveston/property
  rentals` 302-redirects to `/login`; zero listings are visible without a
  session. A login is mandatory.
- **Playwright drives FB fine through the env proxy** (needs
  `ignoreHTTPSErrors: true` because the network policy does TLS interception).
- **Headless login from a datacenter IP gets a reCAPTCHA.** The dedicated
  account's password was accepted, but FB immediately served a reCAPTCHA
  "I'm not a robot" challenge at the 2FA step. We will NOT auto-solve CAPTCHAs
  (ToS / access-control circumvention). This confirms the cloud container
  cannot host the scrape.

### Consequence for the build (locks in the architecture)
- Run on the **user's own machine** with a **persistent browser profile**
  (`launchPersistentContext(userDataDir=...)`), and do the **first login
  headed/visible** so the user clears any 2FA + CAPTCHA *as a human, once*.
  Playwright then reuses the saved cookies for all subsequent **headless**
  twice-daily runs — no re-login, no CAPTCHA, on a residential IP.
- The scraper must detect "session expired / re-auth needed" and surface it in
  the email footer so the user knows to re-run the one-time headed login.

> Security note: the dedicated account's password was shared in chat during
> setup. Since it's a throwaway account that's low-risk, but rotate it once the
> machine-side login is working if you want it clean.

---

## 13. Kickoff prompt for Codex

Paste this to Codex, with this `BRIEF.md` (and ideally the `recon/` scripts)
attached:

> Build a self-updating Facebook Marketplace apartment-hunt directory per the
> attached `BRIEF.md`. Read the whole brief; it has the search profile, the
> per-listing schema (incl. derived fields: total upfront cost, specials,
> utilities, commute-to-UTMB, and a bougie /10 rating with the §5 rubric), the
> email format, and — critically — §12, which documents live recon: Marketplace
> requires login, and a headless login from a server IP hits a reCAPTCHA, so the
> scraper MUST run on my machine with a persistent Playwright profile and a
> one-time **headed** login (I clear 2FA/CAPTCHA as a human once), then headless
> twice-daily runs reuse the saved session.
>
> Deliverables:
> 1. A runnable project (Python or Node — your call; recon used Playwright/Node).
> 2. `scrape` (persistent-profile login + Galveston property-rentals search +
>    listing extraction), `filter` (hard rules: in-unit W/D required; budget
>    rule = ≤$1200 if utilities included else ≤$1000), `enrich` (one batched LLM
>    call for the derived fields), `diff` (new-since-last-run + price drops via a
>    JSON state file), `rank`, `render` (skimmable HTML email), `send` (Gmail).
> 3. Scheduling via cron/launchd at 7:30am & 6:00pm America/Chicago.
> 4. A README: how to do the one-time headed login, set the LLM + Gmail
>    credentials, and install the schedule.
> 5. Defensive scraping: retries, clear logging, and "session expired" detection
>    that's surfaced in the email footer.
>
> Use the §9 defaults wherever the brief leaves a choice. Ask me only about the
> Gmail send mechanism (app password vs OAuth) and whether I want a maps API key
> for exact commute times.
