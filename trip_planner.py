#!/usr/bin/env python3
"""
Ad-hoc multi-trip ROUND TRIP planner: every Frontier way from the Bay Area to a
set of trip ideas (TRIPS), GoWild first, Discount Den round trips under $150 second.

Each trip must be away for a whole Saturday and Sunday (no extra PTO for the
weekend) and fit its own date window and length (days counted door to door,
departure and return day included). Coverage, per trip:
  - every Bay Area origin (BAY_AREA), out and back, including coming home to a
    different Bay Area airport;
  - every gateway airport for the place, including open-jaw within a group
    (e.g. into LAS for Death Valley, out of PSP after Joshua Tree);
  - Frontier's own through-tickets (its search already builds its connections)
    plus separate-ticket self-connections through Frontier hubs (trip "hubs");
  - every departure/return date pair the trip's rules allow.

Phases (resumable; data in results/trip_planner/):
  plan       print the search plan and its size; no browser
  calendars  month low-fare calendar per route (one page per route-month)
  screen     candidate trips from the calendars -> shortlist of legs; offline
  flights    exact flight page for every shortlisted leg (times, GoWild, DD)
  report     price real itineraries from the exact pages, save, email
  validate   final review: re-fetch every leg the report lists, re-price each
             itinerary, rule-check it, rebuild the report with the results, email
  all        calendars -> screen -> flights -> validate
  watch      re-check shortlisted legs whose GoWild window is open, report, and
             email when a new GoWild round trip shows up (run daily in the window)

GoWild timing: domestic GoWild opens the day before departure; anything outside
the continental US (incl. Puerto Rico/USVI, as in the scheduled checker) 10 days
before — at midnight local time of the departure airport. So most GoWild fares
for a trip weeks away can't be seen yet: the report lists each shortlisted
trip's opening dates, and `watch` picks fares up as they are released (early
booking fares Frontier offers on select flights are reported whenever seen).
Calendar prices are rounded screening prices; reported totals come only from
exact flight pages. GoWild is dropped on blackout dates; Discount Den is not.

    python3 trip_planner.py plan
    python3 trip_planner.py all [--trips desert,puerto_rico] [--no-email]
    python3 trip_planner.py watch
"""

import argparse
import json
import os
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from itertools import product
from pathlib import Path
from zoneinfo import ZoneInfo

from colombia_itineraries import boundary, fare
from config import DESTINATION_SERVICE_STARTS, is_blackout_date

OUTPUT = Path(__file__).parent / "results" / "trip_planner"
CALENDARS = OUTPUT / "calendars.jsonl"
SHORTLIST = OUTPUT / "shortlist.json"
FLIGHTS = OUTPUT / "flights.jsonl"
WATCH_LAST = OUTPUT / "watch_last.json"

# Frontier came back to Oakland (OAK–LAS) on Aug 20, 2026.
BAY_AREA = ("SFO", "SJC", "OAK")

WINDOW_NOV_DEC = ("2026-11-01", "2026-12-16")  # "mid-December": before the Dec 19 blackouts

TRIPS = {
    "desert": dict(
        title="Death Valley / Joshua Tree",
        gateways={
            "LAS": "Las Vegas (Death Valley ~2h drive)",
            "PSP": "Palm Springs (Joshua Tree ~1h)",
            "ONT": "Ontario (Joshua Tree ~1.5h)",
            "BUR": "Burbank (Joshua Tree ~2.5h)",
            "LAX": "Los Angeles (Joshua Tree ~2.5h)",
        },
        # One group: in at LAS for Death Valley, out of PSP/ONT after Joshua Tree
        # (~4h drive between the parks; one-way car hire usually has a drop fee).
        groups=[("LAS", "PSP", "ONT", "BUR", "LAX")],
        window=WINDOW_NOV_DEC, days=(3, 5), hubs=("DEN",),
    ),
    "puerto_rico": dict(
        title="Puerto Rico",
        gateways={"SJU": "San Juan", "BQN": "Aguadilla", "PSE": "Ponce"},
        groups=[("SJU", "BQN", "PSE")],
        # "At least a full week": 8-10 days door to door (7-9 nights).
        window=WINDOW_NOV_DEC, days=(8, 10),
        hubs=("MCO", "ATL", "PHL", "MIA", "FLL", "ORD", "DEN", "LAS"),
    ),
    "new_orleans": dict(
        title="New Orleans",
        gateways={"MSY": "New Orleans"},
        groups=[("MSY",)],
        window=("2027-01-01", "2027-02-28"), days=(3, 5),
        hubs=("DEN", "LAS", "ATL", "ORD"),
    ),
    "key_west": dict(
        title="Key West",
        gateways={
            "EYW": "Key West",
            "MIA": "Miami (Key West ~3.5-4h drive)",
            "FLL": "Fort Lauderdale (Key West ~4-4.5h)",
        },
        groups=[("EYW", "MIA", "FLL")],
        window=WINDOW_NOV_DEC, days=(3, 5),
        hubs=("DEN", "LAS", "ATL", "MCO", "ORD", "PHL"),
    ),
    "park_city": dict(
        title="Park City",
        gateways={"SLC": "Salt Lake City (Park City ~40 min)"},
        groups=[("SLC",)],
        window=WINDOW_NOV_DEC, days=(3, 5), hubs=("DEN", "LAS"),
    ),
    "latam_caribbean": dict(
        title="Central America / Caribbean / Colombia",
        gateways={
            "SJO": "San Jose, Costa Rica", "LIR": "Liberia, Costa Rica",
            "GUA": "Guatemala City", "SAL": "San Salvador, El Salvador",
            "SAP": "San Pedro Sula, Honduras", "TGU": "Tegucigalpa, Honduras",
            "RTB": "Roatan, Honduras",
            "SDQ": "Santo Domingo, DR", "PUJ": "Punta Cana, DR",
            "STI": "Santiago, DR", "POP": "Puerto Plata, DR",
            "MBJ": "Montego Bay, Jamaica", "KIN": "Kingston, Jamaica",
            "MDE": "Medellin, Colombia", "BOG": "Bogota, Colombia",
            "CTG": "Cartagena, Colombia",
            "STT": "St. Thomas, USVI", "STX": "St. Croix, USVI",
        },
        # Open-jaw only where the two airports are a sensible overland/ferry hop.
        groups=[("SJO", "LIR"), ("GUA", "SAL"), ("SAP", "TGU", "RTB"),
                ("SDQ", "PUJ", "STI", "POP"), ("MBJ", "KIN"),
                ("MDE", "BOG", "CTG"), ("STT", "STX")],
        window=WINDOW_NOV_DEC, days=(3, 5),
        hubs=("MCO", "MIA", "FLL", "ATL", "PHL", "SJU"),
    ),
}

AIRPORT_TZ = {
    **dict.fromkeys(("SFO", "SJC", "OAK", "LAS", "PSP", "ONT", "BUR", "LAX"),
                    "America/Los_Angeles"),
    **dict.fromkeys(("DEN", "SLC"), "America/Denver"),
    **dict.fromkeys(("MSY", "ORD"), "America/Chicago"),
    **dict.fromkeys(("ATL", "MCO", "MIA", "FLL", "PHL", "EYW"), "America/New_York"),
    # Outside the continental US from here on (10-day GoWild window).
    **dict.fromkeys(("SJU", "BQN", "PSE", "STT", "STX"), "America/Puerto_Rico"),
    **dict.fromkeys(("SJO", "LIR"), "America/Costa_Rica"),
    "GUA": "America/Guatemala",
    "SAL": "America/El_Salvador",
    **dict.fromkeys(("SAP", "TGU", "RTB"), "America/Tegucigalpa"),
    **dict.fromkeys(("SDQ", "PUJ", "STI", "POP"), "America/Santo_Domingo"),
    **dict.fromkeys(("MBJ", "KIN"), "America/Jamaica"),
    **dict.fromkeys(("MDE", "BOG", "CTG"), "America/Bogota"),
}
CONUS_TZS = {"America/Los_Angeles", "America/Denver", "America/Chicago", "America/New_York"}

# Weekdays most offices close, so they cost no PTO.
DAYS_OFF = {"2026-11-26", "2026-11-27", "2026-12-25", "2027-01-01",
            "2027-01-18", "2027-02-15"}

DD_TARGET = 150          # Discount Den round trips under this are called out
DD_SCREEN_MAX = 175      # calendar prices are rounded; screen with some slack
MIN_CONNECT_HOURS = 3    # separate tickets: re-check bags, absorb delays
MIN_CONNECT_INTL = 4     # ...plus immigration/customs coming back into the US
MAX_CONNECT_HOURS = 24
PAGE_DELAY = int(os.environ.get("TRIP_PAGE_DELAY", "6"))
MAX_FAILURES = 6         # consecutive blocked/error pages before stopping (resume later)
# Ranking for the overall picks: dollars per PTO day / travel hour / extra ticket.
SCORE_PTO, SCORE_HOUR, SCORE_SELF_CONNECT, SCORE_OPEN_JAW = 60, 5, 20, 10


# --- Dates and GoWild windows ------------------------------------------------
def _d(s):
    return date.fromisoformat(s)


def _fmt(day):
    return f"{day:%a %b} {day.day}"


def spans_weekend(first, last):
    """True if away for a whole Saturday and Sunday between first and last."""
    sat = first + timedelta(days=(5 - first.weekday()) % 7)
    return sat + timedelta(days=1) <= last


def served_from(gateway):
    start = DESTINATION_SERVICE_STARTS.get(gateway)
    return _d(start) if start else date.min


def date_pairs(trip, gateway=None):
    """Every (leave, return) date pair allowed by the trip's window/length/weekend
    rules; with a gateway, only pairs on or after its service start."""
    start, end = map(_d, trip["window"])
    if gateway:
        start = max(start, served_from(gateway))
    lo, hi = trip["days"]
    pairs = []
    day = start
    while day <= end:
        for n in range(lo, hi + 1):
            back = day + timedelta(days=n - 1)
            if back <= end and spans_weekend(day, back):
                pairs.append((day, back))
        day += timedelta(days=1)
    return pairs


def non_conus(code):
    return AIRPORT_TZ.get(code, "America/Los_Angeles") not in CONUS_TZS


def gowild_lead(origin, dest):
    return 10 if non_conus(origin) or non_conus(dest) else 1


def gowild_opens(origin, dest, day):
    """Local date (at the departure airport) on which GoWild for `day` opens."""
    return day - timedelta(days=gowild_lead(origin, dest))


def gowild_window_open(origin, dest, day, now):
    today = now.astimezone(ZoneInfo(AIRPORT_TZ.get(origin, "America/Los_Angeles"))).date()
    return gowild_opens(origin, dest, day) <= today <= day


def _months(trip, gateway):
    """Months to search for a gateway: from its service start (if later than the
    window start) to the window end. A gateway with no outbound date pairs can
    still be an open-jaw return (into MDE, out of BOG)."""
    start, last = map(_d, trip["window"])
    first = max(start, served_from(gateway))
    if first > last:
        return []
    months, y, m = [], first.year, first.month
    while (y, m) <= (last.year, last.month):
        months.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


# --- Plan ---------------------------------------------------------------------
def calendar_jobs(trip_keys, self_connect=True):
    """Route-month calendar pages to fetch: direct routes first, hub legs after."""
    direct, hub_legs, seen = [], [], set()

    def add(bucket, origin, dest, months):
        for month in months:
            if (origin, dest, month) not in seen:
                seen.add((origin, dest, month))
                bucket.append(dict(origin=origin, destination=dest, month=month))

    for key in trip_keys:
        trip = TRIPS[key]
        for gw in trip["gateways"]:
            months = _months(trip, gw)
            for bay in BAY_AREA:
                add(direct, bay, gw, months)
                add(direct, gw, bay, months)
            if not self_connect:
                continue
            for hub in trip["hubs"]:
                if hub == gw or not months:
                    continue
                add(hub_legs, hub, gw, months)
                add(hub_legs, gw, hub, months)
                for bay in BAY_AREA:
                    add(hub_legs, bay, hub, months)
                    add(hub_legs, hub, bay, months)
    return direct + hub_legs


def print_plan(trip_keys, self_connect):
    print("=" * 64)
    print("FRONTIER TRIP PLANNER — SEARCH PLAN")
    print(f"Bay Area origins: {', '.join(BAY_AREA)}")
    print("=" * 64)
    for key in trip_keys:
        trip = TRIPS[key]
        pairs = date_pairs(trip)
        weekends = sorted({a + timedelta(days=(5 - a.weekday()) % 7) for a, _ in pairs})
        print(f"\n{trip['title']} [{key}]")
        print(f"  Window {trip['window'][0]} to {trip['window'][1]}; "
              f"{trip['days'][0]}-{trip['days'][1]} days incl. a full weekend")
        print(f"  {len(pairs)} date pairs over {len(weekends)} weekends: "
              + ", ".join(_fmt(s) for s in weekends))
        for gw, name in trip["gateways"].items():
            n = len(date_pairs(trip, gw))
            note = "" if n == len(pairs) else f"  ({n} pairs; service from {served_from(gw)})"
            print(f"    {gw}  {name}{note}")
        print(f"  Self-connect hubs: {', '.join(trip['hubs']) if self_connect else 'off'}")
    jobs = calendar_jobs(trip_keys, self_connect)
    n_direct = len(calendar_jobs(trip_keys, False))
    print(f"\nCalendar pages: {len(jobs)} ({n_direct} through-ticket routes, "
          f"{len(jobs) - n_direct} self-connect hub legs)")
    print(f"Rough calendar-phase time at ~{PAGE_DELAY + 9}s/page: "
          f"{len(jobs) * (PAGE_DELAY + 9) / 3600:.1f} h (resumable)")


# --- Fetching -------------------------------------------------------------------
def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run_jobs(jobs, path, fetch, key_fields, done_statuses=("ok",),
             fail_statuses=("blocked", "error"), refresh=False):
    """Fetch each job not already recorded with a done status; append to path.
    A captcha gets one backoff + fresh browser; MAX_FAILURES fail_statuses in a
    row stops the run (re-run to resume)."""
    from gowild_deal_report import CAPTCHA_BACKOFF, _restart_driver, build_driver

    OUTPUT.mkdir(parents=True, exist_ok=True)
    done = set()
    if not refresh:
        done = {tuple(r[k] for k in key_fields) for r in read_jsonl(path)
                if r["status"] in done_statuses}
    todo = [j for j in jobs if tuple(j[k] for k in key_fields) not in done]
    print(f"{len(todo)} pages to fetch ({len(jobs) - len(todo)} already done)", flush=True)
    if not todo:
        return
    driver = build_driver()
    failures = 0
    try:
        driver.set_page_load_timeout(45)
        driver.get("https://www.flyfrontier.com/")
        time.sleep(5)
        for index, job in enumerate(todo, 1):
            try:
                r = fetch(driver, job)
                if r["status"] == "blocked":
                    print("  captcha; backing off with a fresh browser...", flush=True)
                    time.sleep(CAPTCHA_BACKOFF)
                    driver = _restart_driver(driver)
                    driver.set_page_load_timeout(45)
                    r = fetch(driver, job)
            except Exception as exc:
                r = dict(job, status="error", error=type(exc).__name__,
                         checked_at=datetime.now().astimezone().isoformat())
                try:
                    driver = _restart_driver(driver)
                    driver.set_page_load_timeout(45)
                except Exception:
                    pass
            with path.open("a") as out:
                out.write(json.dumps(r) + "\n")
            if "error" in r:
                detail = r["error"]
            elif "days" in r:
                detail = f"{sum(d['available'] for d in r['days'])} days available"
            else:
                detail = f"{len(r.get('flights') or [])} flights"
            print(f"[{index}/{len(todo)}] {' '.join(job[k] for k in key_fields)}: "
                  f"{r['status']}, {detail}", flush=True)
            failures = failures + 1 if r["status"] in fail_statuses else 0
            if failures >= MAX_FAILURES:
                print("Stopping after repeated blocks/errors; re-run to resume.", flush=True)
                break
            time.sleep(PAGE_DELAY)
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def fetch_calendars(trip_keys, self_connect, refresh=False):
    from colombia_trip_search import fetch_calendar

    def fetch(driver, job):
        year, month = map(int, job["month"].split("-"))
        return fetch_calendar(driver, job["origin"], job["destination"], year, month,
                              evidence_dir=None, timeout=35)

    # no_service (an empty calendar), a calendar that never renders, or a 406
    # is a market Frontier doesn't sell: record it, don't retry or count it.
    run_jobs(calendar_jobs(trip_keys, self_connect), CALENDARS, fetch,
             ("origin", "destination", "month"),
             ("ok", "no_service", "unverified", "http_error"), ("blocked", "error"), refresh)


def fetch_flights(jobs, refresh=False):
    from colombia_search import search

    # Shortlisted legs come from calendar availability, so any failure is real.
    run_jobs(jobs, FLIGHTS, lambda driver, job: search(
        driver, job["origin"], job["destination"], _d(job["date"])),
        ("origin", "destination", "date"), ("ok",),
        ("blocked", "error", "http_error"), refresh)


# --- Screening (calendar prices) ---------------------------------------------
def load_calendar_fares(records):
    fares = {}
    for r in records:
        if r["status"] != "ok":
            continue
        for d in r["days"]:
            if d["available"] and d["calendar_price"] is not None:
                fares[(r["origin"], r["destination"], d["date"])] = (
                    d["calendar_price"], bool(d["is_discount_den"]))
    return fares


def _cal_ways(fares, origin, dest, day, hubs, outbound):
    """Cheapest through-ticket and cheapest self-connect origin->dest whose first
    (outbound) or last (return) flight is on `day`: [(price, all_dd, legs)]."""
    def leg(o, d, when):
        hit = fares.get((o, d, when.isoformat()))
        return None if hit is None else (hit, (o, d, when.isoformat()))

    ways = []
    direct = leg(origin, dest, day)
    if direct:
        (price, dd), key = direct
        ways.append((price, dd, (key,)))
    best = None
    for hub in hubs:
        if hub in (origin, dest):
            continue
        if outbound:
            pairs = [(leg(origin, hub, day), leg(hub, dest, day + timedelta(days=k)))
                     for k in (0, 1)]
        else:
            pairs = [(leg(origin, hub, day - timedelta(days=k)), leg(hub, dest, day))
                     for k in (0, 1)]
        for a, b in pairs:
            if a and b:
                way = (a[0][0] + b[0][0], a[0][1] and b[0][1], (a[1], b[1]))
                if best is None or way[0] < best[0]:
                    best = way
    if best:
        ways.append(best)
    return ways


def screen_trip(key, fares, self_connect=True):
    """Calendar-priced candidates: for every date pair x gateway pair, the
    cheapest combination and the cheapest all-Discount-Den combination."""
    trip = TRIPS[key]
    hubs = trip["hubs"] if self_connect else ()
    candidates = []
    for group in trip["groups"]:
        for g_in, g_out in product(group, group):
            for out, back in date_pairs(trip, g_in):
                if back < served_from(g_out):
                    continue
                outs = [(w, bay) for bay in BAY_AREA
                        for w in _cal_ways(fares, bay, g_in, out, hubs, True)]
                backs = [(w, bay) for bay in BAY_AREA
                         for w in _cal_ways(fares, g_out, bay, back, hubs, False)]
                combos = [(a[0] + b[0], a[1] and b[1], a, b, o, h)
                          for (a, o), (b, h) in product(outs, backs)]
                if not combos:
                    continue
                picks = [min(combos, key=lambda c: (c[0], len(c[2][2]) + len(c[3][2])))]
                dd = [c for c in combos if c[1]]
                if dd:
                    picks.append(min(dd, key=lambda c: c[0]))
                for total, all_dd, a, b, origin, home in picks:
                    legs = [dict(origin=o, destination=d, date=day) for o, d, day in a[2] + b[2]]
                    candidates.append(dict(
                        trip=key, out=out.isoformat(), back=back.isoformat(),
                        gateway_in=g_in, gateway_out=g_out, origin=origin, home=home,
                        calendar_total=round(total, 2), all_dd=all_dd,
                        self_connect=len(legs) > 2, legs=legs))
    return candidates


def _distinct(cands, n, key=lambda c: (c["out"], c["back"], c["gateway_in"], c["gateway_out"])):
    out, seen = [], set()
    for c in cands:
        if key(c) not in seen:
            seen.add(key(c))
            out.append(c)
            if len(out) == n:
                break
    return out


def shortlist(candidates, trip_key, top=10, dd_top=10, per_group=3):
    """Cheapest overall, cheapest Discount Den near the target, and the cheapest
    per gateway group and per weekend so every option gets an exact check."""
    ranked = sorted(candidates, key=lambda c: (c["calendar_total"], len(c["legs"])))
    picked = _distinct(ranked, top)
    picked += _distinct([c for c in ranked if c["all_dd"] and c["calendar_total"] <= DD_SCREEN_MAX], dd_top)
    for group in TRIPS[trip_key]["groups"]:
        picked += _distinct([c for c in ranked if c["gateway_in"] in group], per_group)
    weekend = lambda c: (_d(c["out"]) + timedelta(days=(5 - _d(c["out"]).weekday()) % 7))
    picked += _distinct(ranked, 99, key=weekend)
    return _distinct(picked, len(picked), key=lambda c: json.dumps(c, sort_keys=True))


def run_screen(trip_keys, self_connect):
    fares = load_calendar_fares(read_jsonl(CALENDARS))
    if not fares:
        raise SystemExit("No calendar data yet: run `calendars` first.")
    picked = {}
    for key in trip_keys:
        cands = screen_trip(key, fares, self_connect)
        picked[key] = shortlist(cands, key)
        print(f"{TRIPS[key]['title']}: {len(cands)} calendar candidates, "
              f"{len(picked[key])} shortlisted")
    jobs = []
    for cands in picked.values():
        for c in cands:
            for leg in c["legs"]:
                if leg not in jobs:
                    jobs.append(leg)
    SHORTLIST.write_text(json.dumps(dict(trips=picked, jobs=jobs), indent=2))
    print(f"{len(jobs)} exact route/date pages to check")
    return jobs


# --- Itineraries (exact flight pages) ----------------------------------------
def latest_records(records):
    """Latest record per (origin, destination, date); a failed re-check never
    replaces an earlier good one."""
    latest = {}
    for r in records:
        k = (r["origin"], r["destination"], r["date"])
        if r["status"] == "ok" or k not in latest or latest[k]["status"] != "ok":
            latest[k] = r
    return latest


def _local(flight, arrival=False):
    leg = flight["legs"][-1 if arrival else 0]
    return datetime.fromisoformat(leg["arrivalDate" if arrival else "departureDate"][:19])


def _ends(flight):
    return flight["legs"][0]["departureStation"], flight["legs"][-1]["arrivalStation"]


def _min_connect(first):
    o, d = _ends(first)
    return MIN_CONNECT_INTL if non_conus(o) and not non_conus(d) else MIN_CONNECT_HOURS


def _ways(flights_by, origin, dest, day, hubs, outbound):
    """Every way to fly origin->dest whose first (outbound) or last (return)
    flight is on `day`: Frontier's own itineraries plus checked self-connections."""
    get = lambda o, d, when: flights_by.get((o, d, when.isoformat()), [])
    ways = [[f] for f in get(origin, dest, day)]
    for hub in hubs:
        if hub in (origin, dest):
            continue
        if outbound:
            firsts = get(origin, hub, day)
            seconds = get(hub, dest, day) + get(hub, dest, day + timedelta(days=1))
        else:
            firsts = get(origin, hub, day) + get(origin, hub, day - timedelta(days=1))
            seconds = get(hub, dest, day)
        for a, b in product(firsts, seconds):
            gap = (boundary(b) - boundary(a, True)).total_seconds() / 3600
            if _min_connect(a) <= gap <= MAX_CONNECT_HOURS:
                ways.append([a, b])
    return ways


def _price_flight(f, now):
    """(gowild, discount_den, gowild_pending) for one flight."""
    o, d = _ends(f)
    day = _local(f).date()
    if is_blackout_date(day.isoformat()):
        return None, fare(f, "Discount Den"), False
    gw = fare(f, "GoWild")
    return gw, fare(f, "Discount Den"), gw is None and not gowild_window_open(o, d, day, now)


def _price(flights, now):
    """Best total per category for an itinerary's flights:
    {category: (total, [(price or None, kind) per flight])}."""
    priced = [_price_flight(f, now) for f in flights]
    out = {}
    if all(gw is not None for gw, _, _ in priced):
        out["GoWild"] = [(gw, "GoWild") for gw, _, _ in priced]
    if all(dd is not None for _, dd, _ in priced):
        out["Discount Den"] = [(dd, "Discount Den") for _, dd, _ in priced]
    if "GoWild" not in out and all(gw is not None or dd is not None for gw, dd, _ in priced):
        mix = [min((p, k) for p, k in ((gw, "GoWild"), (dd, "Discount Den")) if p is not None)
               for gw, dd, _ in priced]
        if any(k == "GoWild" for _, k in mix):
            out["GoWild + Discount Den"] = mix
    if (any(pending for _, _, pending in priced)
            and all(gw is not None or pending for gw, _, pending in priced)):
        out["GoWild pending"] = [(gw, "GoWild") if gw is not None else (None, "GoWild opens")
                                 for gw, _, _ in priced]
    return {k: (round(sum(p for p, _ in v if p is not None), 2), v) for k, v in out.items()}


def pto_days(leave, home):
    """Weekdays away (DAYS_OFF excluded); an evening departure costs no PTO."""
    n, day = 0, leave.date()
    while day <= home.date():
        if day.weekday() < 5 and day.isoformat() not in DAYS_OFF:
            n += 1
        day += timedelta(days=1)
    first = leave.date()
    if first.weekday() < 5 and first.isoformat() not in DAYS_OFF and leave.hour >= 17:
        n -= 1
    return n


def build_itineraries(trip_key, flights_by, now, self_connect=True):
    """Every round trip the exact pages support for one trip, best per
    (category, dates, gateways)."""
    trip = TRIPS[trip_key]
    hubs = trip["hubs"] if self_connect else ()
    start, end = map(_d, trip["window"])
    lo, hi = trip["days"]
    group_of = {gw: g for g in trip["groups"] for gw in g}
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]

    backs = defaultdict(list)  # (gateway, home arrival date) -> [(home, flights)]
    for gw, home, day in product(trip["gateways"], BAY_AREA, days):
        for way in _ways(flights_by, gw, home, day, hubs, False):
            backs[(gw, _local(way[-1], True).date())].append((home, way))

    best = {}
    for gw, origin, day in product(trip["gateways"], BAY_AREA, days):
        for out in _ways(flights_by, origin, gw, day, hubs, True):
            leave = _local(out[0])
            if leave.date() < max(start, served_from(gw)):
                continue
            for gw_out, n in product(group_of[gw], range(lo, hi + 1)):
                home_day = leave.date() + timedelta(days=n - 1)
                if home_day > end or not spans_weekend(leave.date(), home_day):
                    continue
                for home, back in backs.get((gw_out, home_day), []):
                    if boundary(back[0]) <= boundary(out[-1], True) + timedelta(hours=12):
                        continue
                    _add_itinerary(best, trip_key, origin, gw, gw_out, home, out, back, now)
    return list(best.values())


def _add_itinerary(best, trip_key, origin, g_in, g_out, home, out, back, now):
    flights = out + back
    leave, arrive_home = _local(out[0]), _local(back[-1], True)
    hours = ((boundary(out[-1], True) - boundary(out[0])) +
             (boundary(back[-1], True) - boundary(back[0]))).total_seconds() / 3600
    for category, (total, fares) in _price(flights, now).items():
        item = dict(
            trip=trip_key, category=category, total=total, fares=fares,
            origin=origin, home=home, gateway_in=g_in, gateway_out=g_out,
            out=out, back=back, leave=leave.isoformat(), home_arrival=arrive_home.isoformat(),
            days=(arrive_home.date() - leave.date()).days + 1,
            pto=pto_days(leave, arrive_home), travel_hours=round(hours, 1),
            stops=sum(len(f["legs"]) - 1 for f in flights) + len(out) + len(back) - 2,
            self_connect=len(out) + len(back) > 2,
            open_jaw=origin != home or g_in != g_out)
        item["score"] = _score(item)
        k = (category, leave.date(), arrive_home.date(), g_in, g_out)
        rank = (lambda i: (i["pto"], i["travel_hours"], i["total"])) if category == "GoWild pending" \
            else (lambda i: (i["total"], i["pto"], i["open_jaw"], i["travel_hours"]))
        if k not in best or rank(item) < rank(best[k]):
            best[k] = item


def _score(item):
    return (item["total"] + SCORE_PTO * item["pto"] + SCORE_HOUR * item["travel_hours"]
            + SCORE_SELF_CONNECT * item["self_connect"] + SCORE_OPEN_JAW * item["open_jaw"])


# --- Report -------------------------------------------------------------------
def _distinct_trips(items, n):
    return _distinct(items, n, key=lambda i: (i["leave"][:10], i["home_arrival"][:10],
                                              i["gateway_in"], i["gateway_out"]))


def rank_trip(items):
    cheapest = lambda i: (i["total"], i["pto"], i["open_jaw"], i["travel_hours"])
    gowild = sorted((i for i in items if i["category"] in ("GoWild", "GoWild + Discount Den")),
                    key=lambda i: (i["category"] != "GoWild",) + cheapest(i))
    dd = sorted((i for i in items if i["category"] == "Discount Den"), key=cheapest)
    pending = sorted((i for i in items if i["category"] == "GoWild pending"),
                     key=lambda i: (i["pto"], i["travel_hours"], i["stops"]))
    return dict(gowild=_distinct_trips(gowild, 5),
                dd_target=_distinct_trips([i for i in dd if i["total"] < DD_TARGET], 5),
                dd_any=_distinct_trips(dd, 5),
                pending=_distinct_trips(pending, 5))


def _flight_lines(label, flights, fares, now):
    lines = []
    for f, (price, kind) in zip(flights, fares):
        o, d = _ends(f)
        stations = "→".join([f["legs"][0]["departureStation"]] +
                            [leg["arrivalStation"] for leg in f["legs"]])
        dep, arr = _local(f), _local(f, True)
        nums = "/".join(f"F9 {leg.get('flightNumber', '?')}" for leg in f["legs"])
        if price is None:
            opens = gowild_opens(o, d, dep.date())
            cost = f"GoWild opens {_fmt(opens)} ({o} midnight)"
        else:
            cost = f"${price:.2f} {kind}"
            if kind == "GoWild" and not gowild_window_open(o, d, dep.date(), now):
                cost += " (early-booking release; fee may apply)"
        arr_note = "" if arr.date() == dep.date() else f" (+{(arr.date() - dep.date()).days}d)"
        lines.append(f"      {label} {_fmt(dep)} {stations} {dep:%H:%M}→{arr:%H:%M}{arr_note} "
                     f"| {nums} | {cost} | {f.get('stopsText', '')} {f.get('duration', '')}".rstrip())
        label = "    "
    return lines


def _trip_lines(rank, i, now, tag=""):
    trip = TRIPS[i["trip"]]
    leave, home = _d(i["leave"][:10]), _d(i["home_arrival"][:10])
    route_in = trip["gateways"][i["gateway_in"]].split(" (")[0]
    gws = i["gateway_in"] if i["gateway_in"] == i["gateway_out"] else \
        f"{i['gateway_in']} in / {i['gateway_out']} out"
    homes = i["origin"] if i["origin"] == i["home"] else f"{i['origin']}/{i['home']}"
    price = "GoWild TBD" if i["category"] == "GoWild pending" and not i["total"] else \
        f"${i['total']:.2f}" + (" so far" if i["category"] == "GoWild pending" else "")
    head = (f"{rank:>3}. {price} {i['category']}{tag} — {homes} ⇄ {gws} ({route_in}) | "
            f"{_fmt(leave)} → {_fmt(home)} · {i['days']} days · est. PTO {i['pto']}")
    extras = []
    if i["self_connect"]:
        extras.append("separate tickets via a hub")
    if i["origin"] != i["home"]:
        extras.append("returns to a different Bay Area airport")
    if i["stops"] == 0:
        extras.append("nonstop both ways")
    lines = [head + (f"  [{'; '.join(extras)}]" if extras else "")]
    n = len(i["out"])
    lines += _flight_lines("OUT ", i["out"], i["fares"][:n], now)
    lines += _flight_lines("BACK", i["back"], i["fares"][n:], now)
    return lines


def build_report(by_trip, coverage, now, validation=None):
    out = ["=" * 64, "FRONTIER TRIP PLANNER — BAY AREA ROUND TRIPS", "=" * 64,
           f"Generated {now.astimezone(ZoneInfo('America/Los_Angeles')):%Y-%m-%d %H:%M %Z}. "
           "One adult; fares as quoted by Frontier incl. taxes/fees; not booked.",
           "Every trip spans a full Saturday + Sunday. Days are door to door. PTO "
           "assumes Thanksgiving Thu/Fri, Dec 25, Jan 1, MLK and Presidents' Day off, "
           "and no PTO for a weekday departure at/after 17:00.",
           "GoWild opens 1 day before domestic departures and 10 days before "
           "anything outside the continental US (midnight at the departure "
           "airport); trips listed as 'GoWild pending' have flights on sale "
           "now and the date GoWild opens on each leg.", ""]
    picks = []
    for key, items in by_trip.items():
        trip, ranked = TRIPS[key], rank_trip(items)
        out += ["", "#" * 64, f"{trip['title'].upper()}",
                f"{trip['window'][0]} to {trip['window'][1]} · {trip['days'][0]}-{trip['days'][1]} days · "
                f"via {', '.join(trip['gateways'])}", "#" * 64]
        out.append("\nTop 5 GoWild round trips (all-GoWild first, then GoWild + Discount Den):")
        out += [line for r, i in enumerate(ranked["gowild"], 1) for line in _trip_lines(r, i, now)] \
            or ["   (no GoWild fares released yet for these dates — see the watch list)"]
        out.append(f"\nDiscount Den round trips under ${DD_TARGET}:")
        out += [line for r, i in enumerate(ranked["dd_target"], 1) for line in _trip_lines(r, i, now)] \
            or [f"   (none under ${DD_TARGET})"]
        if not ranked["dd_target"] and ranked["dd_any"]:
            out.append("\nCheapest Discount Den round trips found:")
            out += [line for r, i in enumerate(ranked["dd_any"], 1) for line in _trip_lines(r, i, now)]
        if ranked["pending"]:
            out.append("\nGoWild watch list (best schedules; GoWild not released yet):")
            out += [line for r, i in enumerate(ranked["pending"], 1) for line in _trip_lines(r, i, now)]
        priced = ranked["gowild"] + ranked["dd_target"] + ranked["dd_any"]
        if priced:
            picks.append(min(priced, key=lambda i: i["score"]))
        elif ranked["pending"]:
            picks.append(ranked["pending"][0])

    out += ["", "=" * 64, "OVERALL TOP 3 — THE BEST TRIPS", "=" * 64,
            f"Score = total fare + ${SCORE_PTO}/PTO day + ${SCORE_HOUR}/hour flying "
            f"+ ${SCORE_SELF_CONNECT} separate tickets + ${SCORE_OPEN_JAW} open-jaw "
            "(priced trips first; best per destination)."]
    picks.sort(key=lambda i: (i["category"] == "GoWild pending", i["score"]))
    out += [line for r, i in enumerate(picks[:3], 1)
            for line in _trip_lines(r, i, now, tag=f" · {TRIPS[i['trip']]['title']}")] \
        or ["   (no itineraries found)"]

    if validation:
        out += ["", "-" * 64, "VALIDATION (final review)"] + validation
    out += ["", "-" * 64, "COVERAGE"]
    out += coverage
    out += ["Booking links: https://booking.flyfrontier.com/Flight/InternalSelect?"
            "o1=<FROM>&d1=<TO>&dd1=<YYYY-MM-DD>&ADT=1&mon=true&promo=",
            "Self-connections are separate tickets: a missed connection is not protected.",
            f"Data: {OUTPUT}"]
    return "\n".join(out) + "\n"


def coverage_lines(trip_keys, flights_by_status, cal_records, n_items):
    cal = Counter(r["status"] for r in cal_records)
    lines = [f"Trips: {', '.join(TRIPS[k]['title'] for k in trip_keys)}",
             f"Bay Area origins: {', '.join(BAY_AREA)}; open-jaw home allowed",
             "Calendar pages: " + (", ".join(f"{v} {k}" for k, v in sorted(cal.items())) or "none"),
             "Exact flight pages: " + (", ".join(f"{v} {k}" for k, v in sorted(flights_by_status.items())) or "none"),
             f"Priced/pending itineraries considered: {n_items}"]
    if cal.get("blocked") or flights_by_status.get("blocked"):
        lines.append("⚠️  Some pages were captcha-blocked: results are PARTIAL (re-run to fill in).")
    return lines


def build_all(trip_keys, self_connect, now):
    """(itineraries per trip, flights by (origin, dest, date), page statuses)
    from the latest exact flight pages."""
    latest = latest_records(read_jsonl(FLIGHTS))
    flights_by = {k: r["flights"] for k, r in latest.items() if r["status"] == "ok"}
    by_trip = {k: build_itineraries(k, flights_by, now, self_connect) for k in trip_keys}
    return by_trip, flights_by, Counter(r["status"] for r in latest.values())


def make_report(trip_keys, self_connect, now=None, built=None, validation=None):
    now = now or datetime.now(timezone.utc)
    by_trip, _, statuses = built or build_all(trip_keys, self_connect, now)
    coverage = coverage_lines(trip_keys, statuses, read_jsonl(CALENDARS),
                              sum(len(v) for v in by_trip.values()))
    report = build_report(by_trip, coverage, now, validation)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / f"report_{now.astimezone():%Y%m%d_%H%M%S}.txt"
    path.write_text(report)
    print(report)
    print(f"💾 Saved report to {path}")
    return report, by_trip, statuses


# --- Validation (final review) -------------------------------------------------
def _flight_id(f):
    return "/".join(f"{leg.get('flightNumber')}@{leg['departureStation']}{leg['departureDate'][:16]}"
                    for leg in f["legs"])


def _itinerary_id(i):
    return i["category"] + "|" + ",".join(_flight_id(f) for f in i["out"] + i["back"])


def shown_items(by_trip):
    """Every itinerary the report can list, overall picks included."""
    shown = []
    for items in by_trip.values():
        r = rank_trip(items)
        shown += r["gowild"] + r["dd_target"] + r["dd_any"] + r["pending"]
    return _distinct(shown, len(shown), key=_itinerary_id)


def reprice(item, flights_by, now):
    """The item's total in its category from fresh pages, or None if a flight
    or that fare type is no longer offered."""
    fresh = []
    for f in item["out"] + item["back"]:
        o, d = _ends(f)
        match = [g for g in flights_by.get((o, d, f["legs"][0]["departureDate"][:10]), [])
                 if _flight_id(g) == _flight_id(f)]
        if not match:
            return None
        fresh.append(match[0])
    hit = _price(fresh, now).get(item["category"])
    return hit[0] if hit else None


def rule_problems(item):
    """Independent re-check of one itinerary against the trip's rules."""
    trip = TRIPS[item["trip"]]
    start, end = map(_d, trip["window"])
    lo, hi = trip["days"]
    leave, home = _d(item["leave"][:10]), _d(item["home_arrival"][:10])
    problems = []
    if leave < max(start, served_from(item["gateway_in"])) or home > end:
        problems.append("outside the trip's date window")
    if (home - leave).days + 1 != item["days"] or not lo <= item["days"] <= hi:
        problems.append(f"{item['days']} days is outside {lo}-{hi}")
    if not spans_weekend(leave, home):
        problems.append("doesn't cover a full Saturday + Sunday")
    if not any(item["gateway_in"] in g and item["gateway_out"] in g for g in trip["groups"]):
        problems.append("open-jaw between gateways in different groups")
    for label, way, frm, to in (("out", item["out"], item["origin"], item["gateway_in"]),
                                ("back", item["back"], item["gateway_out"], item["home"])):
        stations = [frm]
        for f in way:
            legs = f["legs"]
            if legs[0]["departureStation"] != stations[-1] or any(
                    a["arrivalStation"] != b["departureStation"] for a, b in zip(legs, legs[1:])):
                problems.append(f"{label} routing doesn't connect")
            stations.append(legs[-1]["arrivalStation"])
        if stations[-1] != to:
            problems.append(f"{label} ends at {stations[-1]}, not {to}")
        for a, b in zip(way, way[1:]):
            gap = (boundary(b) - boundary(a, True)).total_seconds() / 3600
            if not _min_connect(a) <= gap <= MAX_CONNECT_HOURS:
                problems.append(f"{label} self-connection of {gap:.1f}h")
    if item["origin"] not in BAY_AREA or item["home"] not in BAY_AREA:
        problems.append("doesn't start and end in the Bay Area")
    flights = item["out"] + item["back"]
    if any(boundary(b) <= boundary(a, True) for a, b in zip(flights, flights[1:])):
        problems.append("flights out of order")
    for f, (price, kind) in zip(flights, item["fares"]):
        if kind == "GoWild" and price is not None and is_blackout_date(_local(f).date().isoformat()):
            problems.append(f"GoWild on blackout date {_local(f).date()}")
        if price is not None and price <= 0:
            problems.append("non-positive fare")
    if abs(sum(p for p, _ in item["fares"] if p is not None) - item["total"]) > 0.01:
        problems.append("total doesn't match its fares")
    return problems


def _short(i):
    leave, home = _d(i["leave"][:10]), _d(i["home_arrival"][:10])
    return (f"{TRIPS[i['trip']]['title']}: {i['origin']}→{i['gateway_in']} {_fmt(leave)}, "
            f"{i['gateway_out']}→{i['home']} {_fmt(home)} ({i['category']})")


def validation_lines(shown, n_legs, built, now):
    """Compare what the first pass listed against fresh pages, then rule-check
    everything the rebuilt report lists."""
    by_trip, flights_by, _ = built
    priced = [i for i in shown if i["category"] != "GoWild pending"]
    confirmed, changed, gone = 0, [], []
    for i in priced:
        new = reprice(i, flights_by, now)
        if new is None:
            gone.append(i)
        elif abs(new - i["total"]) < 0.005:
            confirmed += 1
        else:
            changed.append((i, new))
    when = now.astimezone(ZoneInfo("America/Los_Angeles"))
    lines = [f"Re-fetched {n_legs} flight pages behind the {len(shown)} itineraries of the first "
             f"pass at {when:%Y-%m-%d %H:%M %Z}; everything above is rebuilt from those fresh pages.",
             f"Fares re-checked: {confirmed} unchanged, {len(changed)} changed, "
             f"{len(gone)} no longer offered (of {len(priced)} priced itineraries)."]
    lines += [f"  ⚠️  {_short(i)}: ${i['total']:.2f} → ${new:.2f}" for i, new in changed]
    lines += [f"  ✖  {_short(i)}: flight or fare no longer offered" for i in gone]
    final = shown_items(by_trip)
    problems = [(i, p) for i in final for p in rule_problems(i)]
    lines.append(f"Rule checks on all {len(final)} listed itineraries (window, length, full weekend, "
                 "routing, connection times, blackout dates, totals): "
                 + ("all passed." if not problems else f"{len(problems)} problem(s):"))
    lines += [f"  ✖  {_short(i)}: {p}" for i, p in problems]
    return lines


def run_validate(trip_keys, self_connect, fetch=None):
    """Final review: re-fetch every leg the report would list, then rebuild the
    report from fresh pages with a validation section. Returns make_report's result."""
    first = build_all(trip_keys, self_connect, datetime.now(timezone.utc))
    shown = shown_items(first[0])
    legs = []
    for i in shown:
        for f in i["out"] + i["back"]:
            o, d = _ends(f)
            leg = dict(origin=o, destination=d, date=f["legs"][0]["departureDate"][:10])
            if leg not in legs:
                legs.append(leg)
    print(f"Validation: re-checking {len(legs)} legs behind {len(shown)} itineraries", flush=True)
    (fetch or fetch_flights)(legs, refresh=True)
    now = datetime.now(timezone.utc)
    built = build_all(trip_keys, self_connect, now)
    return make_report(trip_keys, self_connect, now, built,
                       validation_lines(shown, len(legs), built, now))


def _signature(i):
    return "|".join([i["category"], f"{i['total']:.2f}", i["leave"], i["home_arrival"],
                     i["origin"], i["gateway_in"], i["gateway_out"], i["home"]])


def email_report(report, by_trip, statuses):
    from gowild_deal_report import load_env, send_email

    gw = sum(len(rank_trip(v)["gowild"]) for v in by_trip.values())
    dd = sum(len(rank_trip(v)["dd_target"]) for v in by_trip.values())
    partial = "[PARTIAL] " if statuses.get("blocked") else ""
    send_email(f"{partial}Frontier Trip Planner — {gw} GoWild / {dd} Discount Den "
               f"<${DD_TARGET} round trips", report, load_env())


def watch_due(jobs, latest, now):
    """Shortlisted legs whose GoWild window is open and that haven't been
    checked yet today (by the departure airport's date)."""
    due = []
    for j in jobs:
        if not gowild_window_open(j["origin"], j["destination"], _d(j["date"]), now):
            continue
        tz = ZoneInfo(AIRPORT_TZ.get(j["origin"], "America/Los_Angeles"))
        r = latest.get((j["origin"], j["destination"], j["date"]))
        if r and r["status"] == "ok" and \
                datetime.fromisoformat(r["checked_at"]).astimezone(tz).date() == now.astimezone(tz).date():
            continue
        due.append(j)
    return due


# --- Main ---------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=("plan", "calendars", "screen", "flights", "report",
                                      "validate", "all", "watch"))
    ap.add_argument("--trips", default=",".join(TRIPS), help="comma list of: " + ", ".join(TRIPS))
    ap.add_argument("--no-self-connect", action="store_true", help="through-tickets only")
    ap.add_argument("--refresh", action="store_true", help="re-fetch pages already recorded")
    ap.add_argument("--no-email", action="store_true")
    args = ap.parse_args()
    trip_keys = [k.strip() for k in args.trips.split(",") if k.strip()]
    unknown = [k for k in trip_keys if k not in TRIPS]
    if unknown:
        ap.error(f"unknown trips: {', '.join(unknown)}")
    self_connect = not args.no_self_connect

    if args.phase == "plan":
        print_plan(trip_keys, self_connect)
        return
    if args.phase in ("calendars", "all"):
        fetch_calendars(trip_keys, self_connect, args.refresh)
    if args.phase in ("screen", "all"):
        jobs = run_screen(trip_keys, self_connect)
    if args.phase in ("flights", "all"):
        if args.phase == "flights":
            jobs = json.loads(SHORTLIST.read_text())["jobs"]
        fetch_flights(jobs, args.refresh)
    if args.phase == "watch":
        jobs = json.loads(SHORTLIST.read_text())["jobs"]
        due = watch_due(jobs, latest_records(read_jsonl(FLIGHTS)), datetime.now(timezone.utc))
        print(f"{len(due)} shortlisted legs inside their GoWild window", flush=True)
        fetch_flights(due, refresh=True)
    if args.phase in ("report", "validate", "all", "watch"):
        if args.phase in ("validate", "all"):
            report, by_trip, statuses = run_validate(trip_keys, self_connect)
        else:
            report, by_trip, statuses = make_report(trip_keys, self_connect)
        if args.no_email:
            return
        if args.phase == "watch":
            current = {_signature(i) for v in by_trip.values() for i in rank_trip(v)["gowild"]}
            seen = set(json.loads(WATCH_LAST.read_text())) if WATCH_LAST.exists() else set()
            WATCH_LAST.write_text(json.dumps(sorted(current | seen)))
            if not current - seen:
                print("No new GoWild round trips since the last watch; email not sent.")
                return
        email_report(report, by_trip, statuses)


if __name__ == "__main__":
    main()
