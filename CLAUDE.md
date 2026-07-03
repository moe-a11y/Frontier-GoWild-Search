# CLAUDE.md — Orientation for future agents

Quick, no-prior-knowledge guide to this repo. Read this first.

## What this project does
Checks **Frontier Airlines flight deals** (GoWild pass fares + Discount Den fares)
from Bay Area origins and reports the cheapest ones. All scripts scrape one endpoint:
```
https://booking.flyfrontier.com/Flight/InternalSelect?o1={ORIGIN}&d1={DEST}&dd1={DATE}&ADT=1&mon=true&promo=
```
The flight JSON is embedded in a `<script>` tag on that page. Relevant fields per flight:
`isGoWildFareEnabled`, `goWildFare`, `goWildFareSeatsRemaining`, `discountDenFare`,
`discountDenFareSeatsRemaining`, `stopsText`, `duration`, `legs[0].departureDateFormatted`.

## ⭐ THE working script: `gowild_deal_report.py`
This is the current, primary, production script. Everything else is older/experimental.

What it does when run:
- For each origin in `config.ORIGINS` (**SFO, SJC**):
  - **Domestic (CONUS)** dests → checks the **next day**
  - **International / non-CONUS** dests → checks **10 days out**
- Skips any date that is a **GoWild blackout date** (`config.GOWILD_BLACKOUT_DATES`).
- Collects **both GoWild and Discount Den** fares.
- Builds **Top 10 GoWild / Top 10 Discount Den / Top 5 international** (cheapest first),
  saves the report to `results/deal_report_*.txt`, and **emails** it.
- Runs **headless** (verified to pass Frontier's PerimeterX bot check with no CAPTCHA).

Run manually:  `python3 gowild_deal_report.py`  (env `DEAL_HEADLESS=0` for a visible window)

### Scheduling (already installed on this Mac)
- **launchd** job `com.frontier.dealcheck`, plist at
  `~/Library/LaunchAgents/com.frontier.dealcheck.plist`.
- Fires **Tue/Wed/Thu at 00:01 local**. launchd runs a missed job on wake (unlike cron);
  the Mac must be awake/asleep-not-off.
- Logs: `results/dealcheck.log` and `results/dealcheck.err.log`.
- Pause: `launchctl unload ~/Library/LaunchAgents/com.frontier.dealcheck.plist`
- Resume: `launchctl load ~/Library/LaunchAgents/com.frontier.dealcheck.plist`

### Email config (required for the email step)
Credentials come from a local **`.env`** (gitignored; template `.env.example`).
Uses Gmail SMTP over SSL (465) with a Gmail **App Password** (not the normal password).
Default recipient: muhammadalinajfi1@gmail.com. If `.env` is missing, the run still
saves the report to `results/` but does not email.

## `config.py` — single source of truth
- `ORIGINS` = ["SFO", "SJC"]
- `INTERNATIONAL_DESTINATIONS` (12) and `DOMESTIC_DESTINATIONS` (16); `SFO_DIRECT_DESTINATIONS`
  is the combined dict used by the older single-shot scripts.
- `GOWILD_BLACKOUT_DATES` (2025–2027). The 2026 list is complete per flyfrontier.com.
  Helper: `is_blackout_date("YYYY-MM-DD")`.

## Environment gotcha (Apple Silicon) — already handled
This is an **arm64 Mac**. undetected-chromedriver (a) downloads an x86_64 driver and
(b) patches the driver binary, which breaks its arm64 code signature → macOS SIGKILL.
`build_driver()` (in both `gowild_deal_report.py` and `gowild_WORKING.py`) fixes this by:
resolving the arm64 chromedriver via Selenium Manager, ad-hoc `codesign`-ing a copy, and
disabling uc's patch step (`uc.Patcher.auto = no-op`). Python is system `/usr/bin/python3`
(3.9) with packages installed via `pip install --user`.

## Why browser automation (not plain requests)
Frontier's booking API is protected by **PerimeterX**. Plain `requests`/`curl_cffi` get
403/CAPTCHA (see `docs/PERIMETERX_ISSUE.md`, `docs/CRITICAL_FINDING.md`). Only a real
(undetected) browser that executes JS gets through. That's why the deal checker uses
undetected-chromedriver.

## Other scripts (older / secondary)
- `gowild_WORKING.py` — interactive browser search from SFO+SJC for tomorrow; manual
  CAPTCHA solving; GoWild only. Good for a quick one-off look.
- `gowild_scraper.py` — original interactive undetected-chromedriver scraper (any origin, prompts).
- `gowild_fast.py`, `gowild_fast_bypass.py`, `roundtrip_*.py` — `requests`/`curl_cffi`
  experiments; **blocked by PerimeterX** in practice. `roundtrip_*` reuse `gowild_fast`.
- `tests/` — probes from the PerimeterX investigation. `docs/` — investigation write-ups.
