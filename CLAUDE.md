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
  - **International / non-CONUS** dests → checks **10, 7, and 4 days out**
    (`INTL_DAYS_OUT`; GoWild int'l opens 10 days before departure, and closer
    dates can carry GoWild fares the 10-day date doesn't)
- Skips any date that is a **GoWild blackout date** (`config.GOWILD_BLACKOUT_DATES`).
- Collects **both GoWild and Discount Den** fares.
- Also pulls **cruise deals** from VacationsToGo via `cruise_deals.py` (see below).
- Builds **Top 10 GoWild / Top 10 Discount Den / Top 5 international / Top 10 cruises**
  (cheapest flights first; cruises by highest savings %), saves the report to
  `results/deal_report_*.txt`, and **emails** it.
- Each flight top-10 reserves **≥5 slots for destinations other than LAS/SLC/DEN**
  (`_top_deals`); those three only fill more slots when fewer than 5 other
  destinations have deals. The int'l top-5 lists **GoWild fares first** (user
  preference); Discount Den only fills leftover slots.
- Flight scraping runs **headless** (verified to pass Frontier's PerimeterX bot check).
- **All dates are Pacific** (`ORIGIN_TZ`): GoWild seats open at midnight local time of
  the *departure* city, so "next day" must be computed in PT whatever the PC's zone.
- A captcha page is detected (not silently read as "0 flights"): the route is retried
  after `CAPTCHA_BACKOFF` with a fresh browser; still-blocked routes are listed in the
  report and the subject gets `[PARTIAL]`. After `MAX_BLOCKED_ROUTES` the rest are skipped.

Run manually:  `python3 gowild_deal_report.py`  (env `DEAL_HEADLESS=0` for a visible window)

## Cruise deals: `cruise_deals.py`
Scrapes the **VacationsToGo** "ticker" (last-minute cruise deals). Filters: highest
"You Save" %, **≤10 nights**, **< $1000**, departing OR ending in **California
(SF/LA/San Diego/any ", CA") or any Florida port**; returns the top 10 with
**≥5 California-touching cruises reserved** (Florida may only fill those slots when
fewer than 5 CA deals exist). Each kept deal's **fastdeal detail page** is also
scraped for its **ports of call**; the report shows stops, **star rating**, and
**Fastdeal id**. Auth: signs in with the member email
(`VTG_EMAIL`, default muhammadalinajfi1@gmail.com) — VacationsToGo lets members in with
just an email; registers once if needed.
- **Weekly cache**: results stored in `results/cruise_deals.json`; a fresh scrape only
  runs if the cache is older than 7 days (`get_cruise_deals(force=...)` to override).
- **Must run headful** — VacationsToGo resets connections to headless Chrome, so
  `scrape_cruise_deals()` forces a visible window. Because of the weekly cache this
  window only appears ~once a week during the scheduled job.
- Run manually: `python3 cruise_deals.py [--force]`

### Scheduling on Windows (current machine, since Sep 26, 2026)
- **Runbook: the `deal-check` project skill** (`.claude/skills/deal-check/SKILL.md`) —
  status checks, exit codes, common failures, run-now.
- Task Scheduler task **"Frontier Deal Check"**, Mon/Tue/Wed **00:01 Pacific** (the
  installer converts to local time: 03:01 on this Eastern-time PC). Registered by
  `windows/install_dealcheck_task.ps1` (re-run it if the project moves or the PC's time
  zone changes: `powershell -ExecutionPolicy Bypass -File windows\install_dealcheck_task.ps1`).
- A crashed run emails "Frontier deal checker FAILED" with the traceback.
- Setup on a fresh machine: `python -m pip install -r requirements.txt`, create `.env`,
  run the installer.
- Action: `pythonw.exe -X utf8 windows\run_dealcheck.pyw` (Python 3.12 at
  `%LOCALAPPDATA%\Programs\Python\Python312\`). The launcher redirects output itself and
  appends to `results/dealcheck.log` / `.err.log`. `-X utf8` is required: the report's
  emoji and ★ can't be written under cp1252.
- Why pythonw and not a `.cmd` wrapper: a console window can be closed (the run dies with
  0xC000013A), and headless Chrome inherits cmd's redirected log handles, so an orphaned
  Chrome keeps the logs locked and the next run fails with PermissionError. If that ever
  recurs, find the holder (Restart Manager / Resource Monitor) and kill that Chrome.
- Missed runs start when available; WakeToRun wakes the PC; `_keep_awake()` blocks idle
  sleep mid-run. Interactive logon only (cruise scrape needs a visible Chrome window), so
  the user must be logged in (locked is fine).
- Pause/resume: `Disable-ScheduledTask` / `Enable-ScheduledTask -TaskName "Frontier Deal Check"`.
- `build_driver()` only does the codesign dance on macOS; the `%-d` strftime format is
  Mac/Linux-only, so use `_fmt_day()` in `gowild_deal_report.py` instead.

### Scheduling on macOS (previous machine)
- **launchd** job `com.frontier.dealcheck`, plist at
  `~/Library/LaunchAgents/com.frontier.dealcheck.plist` (tracked copy:
  `launchd/com.frontier.dealcheck.plist` — if paths change, edit the repo copy,
  re-copy it to `~/Library/LaunchAgents/`, and reload).
- Fires **Tue/Wed/Thu at 00:01 local**. launchd runs a missed job on wake (unlike cron);
  the Mac must be awake/asleep-not-off.
- Logs: `results/dealcheck.log` and `results/dealcheck.err.log`.
- Pause: `launchctl unload ~/Library/LaunchAgents/com.frontier.dealcheck.plist`
- Resume: `launchctl load ~/Library/LaunchAgents/com.frontier.dealcheck.plist`
- ⚠️ The project must live **outside `~/Documents`/`~/Desktop`/`~/Downloads`**: macOS
  TCC blocks launchd-spawned python from those folders ("Operation not permitted"),
  which silently killed every scheduled run the week of Jul 7, 2026. The project now
  lives at `~/Projects/Frontier-GoWild-Search` and the plist points there.

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
- `roundtrip_deal_report.py` — **working** (browser-based, reuses `gowild_deal_report`
  helpers). Ad-hoc round-trip search: `--out` / `--back` date lists, pairs legs into
  round trips ranked by total price, emails the report.
- `buf_watch.py` — **temporary** SFO/SJC→BUF GoWild watch for Sep 17–19, 2026, run by
  its own launchd job `com.frontier.bufwatch` (`launchd/com.frontier.bufwatch.plist`).
  No-ops after 2026-09-17; unload and delete the installed plist once it's over.
- `colombia_*.py` — read-only Colombia (via MCO) trip searches; data in `results/colombia_*/`.
- `gowild_fast.py`, `gowild_fast_bypass.py`, `roundtrip_fast.py`, `roundtrip_search.py` —
  `requests`/`curl_cffi` experiments; **blocked by PerimeterX** in practice. The two
  `roundtrip_fast`/`roundtrip_search` scripts reuse `gowild_fast`.
- `tests/` — probes from the PerimeterX investigation. `docs/` — investigation write-ups.
