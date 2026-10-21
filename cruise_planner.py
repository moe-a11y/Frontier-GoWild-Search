#!/usr/bin/env python3
"""
Cruise + Frontier flights planner: VacationsToGo cruise deals paired with real
Frontier flights from the Bay Area to the embarkation port and home from the
debarkation port, priced for two.

For every cruise in the 90-day ticker that sails in the window from a port
Frontier can reach (PORTS), it checks:
  - getting there: any Frontier way (its own itineraries or self-connections via
    HUBS) from SFO/SJC/OAK that lands by the morning of sailing, allowing for the
    airport-to-port transfer (the day before is safer and flagged as a hotel night);
  - getting home: flights leaving the debarkation airport late enough after the
    ship docks and the transfer, on debark day or the day after (hotel night);
  - fares: you pay the cheaper of GoWild / Discount Den per flight, your partner
    Discount Den (standard if none) — or both of you on Discount Den on one
    booking. The $100 voucher only covers YOUR base fare (non-transferable) and
    must be used to book before it expires, so it is shown, not assumed.
Cruise prices are VacationsToGo's per-person, double-occupancy fares; taxes/port
fees are added when the deal page lists them.

Phases (resumable; flight data shared with trip_planner in results/trip_planner/):
  ticker     full VacationsToGo ticker + each candidate's deal page (needs a
             visible browser: VacationsToGo blocks headless Chrome)
  calendars  Frontier month calendars for port airports not already covered
  flights    exact Frontier pages for every candidate's flight dates
  report     rank cruise + flight packages, save, email
  validate   final review: re-fetch every listed package's flights, then report
  all        ticker -> calendars -> flights -> validate

    python3 cruise_planner.py all [--no-email]
"""

import argparse
import json
import re
from datetime import date, datetime, time as dtime, timedelta, timezone
from itertools import product
from pathlib import Path
from zoneinfo import ZoneInfo

import trip_planner as tp

OUTPUT = Path(__file__).parent / "results" / "cruise_planner"
TICKER = OUTPUT / "ticker_all.json"
DETAILS = OUTPUT / "deal_pages.jsonl"
PAGES = OUTPUT / "deal_pages"
EXTRA = OUTPUT / "extra_sailings.json"  # same shape as ticker deals, with a "source"

WINDOW = (date(2026, 11, 1), date(2026, 12, 31))
MAX_NIGHTS = 10
HUBS = ("DEN", "LAS", "ATL", "MCO", "PHL", "ORD")
EMBARK_BY = dtime(11, 0)        # be at the port by about 11:00 on sailing day
NEEDS_BED_BEFORE = dtime(5, 0)  # landing before this (or the day before) means a hotel night
DOCK = dtime(8, 30)             # ships dock early; allow time to get off and clear
LEAVE_SHIP_BUFFER_H = 4.0       # docking -> flight time, plus the transfer: everyone is off by
                                # ~10:00 and wants ~1.5 h at the airport (lines advise 12:30-2 PM flights)
HOTEL_EST = 150                 # scoring only: a pre/post-cruise hotel night
GRATUITY_EST = 18               # per person per night, added by most lines (shown, not totalled)
PTO_COST, HOUR_COST = tp.SCORE_PTO, tp.SCORE_HOUR

# Port (substring of the ticker's port text) -> [(airport, transfer hours, note)].
# Ports with no entry are skipped (no Frontier service, e.g. Honolulu).
PORTS = {
    "San Francisco": [],  # home port: no flight needed
    "Los Angeles": [("LAX", 0.65, "LAX ~35-40 min"), ("ONT", 1.15, "Ontario ~70 min")],
    "Long Beach": [("LAX", 0.6, "LAX ~35-40 min"), ("ONT", 1.15, "Ontario ~70 min")],
    "San Diego": [("SAN", 0.25, "SAN ~15 min")],
    "Miami": [("MIA", 0.4, "MIA ~15-30 min"), ("FLL", 0.9, "FLL ~45-60 min")],
    "Fort Lauderdale": [("FLL", 0.25, "FLL ~15 min"), ("MIA", 0.75, "MIA ~45 min")],
    "Port Canaveral": [("MCO", 1.0, "Orlando ~1 h")],
    "Tampa": [("TPA", 0.5, "TPA ~25 min")],
    "Jacksonville": [("JAX", 0.5, "JAX ~25 min")],
    "Galveston": [("IAH", 1.5, "Houston IAH ~75-90 min")],  # Frontier doesn't serve Hobby
    "New Orleans": [("MSY", 0.5, "MSY ~30 min")],
    "Mobile": [("MSY", 2.5, "New Orleans ~2 h 30")],
    "San Juan": [("SJU", 0.5, "SJU ~25 min")],
    "Boston": [("BOS", 0.25, "BOS ~15 min")],
    "New York": [("LGA", 0.85, "LaGuardia ~40-60 min"), ("EWR", 0.75, "Newark ~30-60 min")],
    "Bayonne": [("EWR", 0.5, "Newark ~30 min")],
}


def port_airports(port):
    for key, airports in PORTS.items():
        if key in port:
            return airports
    return None


def sail_date(text):
    """Ticker sail dates have no year: the ticker covers the next 90 days."""
    month, day = datetime.strptime(text + " 2000", "%b %d %Y").timetuple()[1:3]
    return date(2027 if month < 10 else 2026, month, day)


def candidates(deals):
    """Cruises in the window, <= MAX_NIGHTS, from and to reachable ports."""
    out = []
    for d in deals:
        if not d.get("nights") or d["nights"] > MAX_NIGHTS or not d.get("now"):
            continue
        sail = sail_date(d["sail"])
        if not WINDOW[0] <= sail <= WINDOW[1]:
            continue
        if port_airports(d["from"]) is None or port_airports(d["to"]) is None:
            continue
        out.append(dict(d, sail_date=sail.isoformat(),
                        debark_date=(sail + timedelta(days=d["nights"])).isoformat()))
    return out


# --- Ticker + deal pages (VacationsToGo) ----------------------------------------
def parse_deal_page(html):
    """Ports of call and the cheapest VacationsToGo rate per cabin type. The page
    states its prices already include port charges and government taxes/fees."""
    import cruise_deals as cd

    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    # Two layouts: "Cheapest Inside $X Vacations To Go Rate $Y" / "Brochure Inside $X Our Inside $Y".
    rates = {kind: int(rate.replace(",", "")) for kind, rate in re.findall(
        r"(?:Cheapest|Brochure) (Inside|Oceanview|Balcony|Suite) \$[\d,]+ "
        r"(?:Vacations To Go Rate|Our (?:Inside|Oceanview|Balcony|Suite)) \$([\d,]+)", text)}
    return dict(ports=cd.parse_itinerary(html), rates=rates,
                taxes_included="include port charges and government taxes" in text)


def scrape_ticker(build_driver, detail_wait=5):
    """Full ticker -> TICKER, then each candidate's deal page -> DETAILS (resumable)."""
    import time

    import cruise_deals as cd

    PAGES.mkdir(parents=True, exist_ok=True)
    driver = build_driver(headless=False)
    try:
        deals = cd.parse_ticker(cd.login_and_load_ticker(driver))
        if deals:
            TICKER.write_text(json.dumps(dict(checked_at=datetime.now().astimezone().isoformat(),
                                              deals=deals), indent=1))
        print(f"{len(deals)} ticker deals")
        done = {r["id"] for r in tp.read_jsonl(DETAILS) if not r.get("error")}
        todo = [c for c in candidates(load_deals()) if c["id"] not in done and c.get("link")]
        print(f"{len(todo)} deal pages to fetch")
        for n, c in enumerate(todo, 1):
            try:
                driver.get(c["link"])
                time.sleep(detail_wait)
                html = driver.page_source
                (PAGES / f"{c['id'].lstrip('#')}.html").write_text(html)
                row = dict(id=c["id"], **parse_deal_page(html))
            except Exception as exc:
                row = dict(id=c["id"], error=type(exc).__name__, ports=[], rates={})
            with DETAILS.open("a") as out:
                out.write(json.dumps(row) + "\n")
            print(f"[{n}/{len(todo)}] {c['id']} {c['from']} {c['sail']}: {len(row['ports'])} stops, "
                  f"rates {row.get('rates')}", flush=True)
    finally:
        driver.quit()


def load_deals():
    """Ticker deals plus EXTRA sailings (cruise-line prices found elsewhere); the
    cheaper listing wins when both have the same ship and date."""
    deals = json.loads(TICKER.read_text())["deals"]
    extra = json.loads(EXTRA.read_text()) if EXTRA.exists() else []
    best = {}
    for d in deals + extra:
        k = (d.get("ship", "").lower(), d["sail"])
        if k not in best or d["now"] < best[k]["now"]:
            best[k] = d
    return list(best.values())


def load_details():
    """Deal-page facts, re-parsed from the saved pages when available."""
    details = {r["id"]: r for r in tp.read_jsonl(DETAILS)}
    for path in PAGES.glob("*.html") if PAGES.exists() else []:
        details["#" + path.stem] = dict(id="#" + path.stem, **parse_deal_page(path.read_text()))
    return details


def with_details(cands, details):
    """Add ports and cabin rates; the deal page was read after the ticker, so its
    cheapest cabin is the price (the ticker's is kept as ticker_now)."""
    out = []
    for c in cands:
        d = details.get(c["id"], {})
        c = dict(c, ports=d.get("ports") or c.get("ports"), rates=d.get("rates") or c.get("rates"))
        if d.get("rates"):
            c["ticker_now"], c["now"] = c["now"], min(d["rates"].values())
        out.append(c)
    return out


# --- Frontier calendars + flight pages ----------------------------------------
def _airports(cands):
    return sorted({a for c in cands for port in (c["from"], c["to"]) for a, _, _ in port_airports(port)})


def calendar_jobs(cands):
    months = sorted({c[k][:7] for c in cands for k in ("sail_date", "debark_date")})
    prev = {(r["origin"], r["destination"], r["month"]) for r in tp.read_jsonl(tp.CALENDARS)}
    jobs = []
    for gw, bay, month in product(_airports(cands), tp.BAY_AREA, months):
        for o, d in ((bay, gw), (gw, bay)):
            if (o, d, month) not in prev:
                jobs.append(dict(origin=o, destination=d, month=month))
    return jobs


def flight_jobs(cands):
    """Exact pages: the day before / day of sailing out, debark day / day after back;
    through-tickets wherever the calendars show the route on sale, plus hub legs."""
    fares = tp.load_calendar_fares(tp.read_jsonl(tp.CALENDARS))
    cal_routes = {(o, d) for o, d, _ in fares}
    jobs, seen = [], set()

    def add(o, d, day):
        k = (o, d, day.isoformat())
        if k in seen:
            return
        # Skip routes the calendars show as not sold; keep unknown routes (no calendar).
        if (o, d) in cal_routes and k not in fares:
            return
        seen.add(k)
        jobs.append(dict(origin=o, destination=d, date=k[2]))

    for c in cands:
        sail, debark = date.fromisoformat(c["sail_date"]), date.fromisoformat(c["debark_date"])
        for gw, _, _ in port_airports(c["from"]):
            for bay, day in product(tp.BAY_AREA, (sail - timedelta(days=1), sail)):
                add(bay, gw, day)
                for hub in HUBS:
                    if hub != gw:
                        add(bay, hub, day)
                        add(hub, gw, day)
        for gw, _, _ in port_airports(c["to"]):
            for bay, day in product(tp.BAY_AREA, (debark, debark + timedelta(days=1))):
                add(gw, bay, day)
                for hub in HUBS:
                    if hub != gw:
                        add(gw, hub, day)
                        add(hub, bay, day)
    # Through-tickets first: they decide most packages.
    jobs.sort(key=lambda j: (j["origin"] in HUBS or j["destination"] in HUBS))
    return jobs


# --- Packages -----------------------------------------------------------------
def _flight_cost(flights, now):
    """For two on these flights: (total, how, you, partner, your_fares) or None."""
    priced = tp._price(flights, now)
    partner = [tp._cash(f) for f in flights]
    options = []
    you = [(v[0], k, v[1]) for k, v in priced.items() if k in ("GoWild", "GoWild + Discount Den", "Discount Den")]
    for total, kind, fares in you:
        if None not in partner:
            options.append((round(total + sum(partner), 2), f"you {kind} + partner DD", total,
                            round(sum(partner), 2), fares))
    dd = priced.get("Discount Den")
    if dd and all((tp._seats_left(f.get("discountDenFareSeatsRemaining")) or 2) >= 2 for f in flights):
        options.append((round(2 * dd[0], 2), "both Discount Den", dd[0], dd[0], dd[1]))
    return min(options, key=lambda o: o[0]) if options else None


def cruise_packages(cruise, flights_by, now, keep=3):
    sail, debark = date.fromisoformat(cruise["sail_date"]), date.fromisoformat(cruise["debark_date"])
    cruise_two = 2 * cruise["now"]
    ins, outs_ = port_airports(cruise["from"]), port_airports(cruise["to"])
    # A Bay Area port needs no flight on that end: one empty "way".
    ways_out = [] if ins else [([], "sails from the Bay Area", False)]
    for (gw, transfer, note), bay in product(ins, tp.BAY_AREA):
        latest = datetime.combine(sail, EMBARK_BY) - timedelta(hours=transfer)
        for day in (sail - timedelta(days=1), sail):
            for way in tp._ways(flights_by, bay, gw, day, HUBS, True):
                arrive = tp._local(way[-1], True)
                if arrive <= latest:
                    ways_out.append((way, note, arrive < datetime.combine(sail, NEEDS_BED_BEFORE)))
    ways_back = [] if outs_ else [([], "ends in the Bay Area", False)]
    for (gw, transfer, note), bay in product(outs_, tp.BAY_AREA):
        earliest = datetime.combine(debark, DOCK) + timedelta(hours=LEAVE_SHIP_BUFFER_H + transfer)
        for day in (debark, debark + timedelta(days=1)):
            for way in tp._ways(flights_by, gw, bay, day, HUBS, False):
                if tp._local(way[0]) >= earliest:
                    ways_back.append((way, note, tp._local(way[0]).date() > debark))
    best = []
    for (out, out_note, hotel_out), (back, back_note, hotel_back) in product(
            _prune(ways_out, now), _prune(ways_back, now)):
        flights = out + back
        cost = _flight_cost(flights, now) if flights else (0.0, "no flights", 0.0, 0.0, [])
        if not cost:
            continue
        flights_two, how, you, partner, fares = cost
        leave = tp._local(out[0]) if out else datetime.combine(sail, dtime(12))
        home = tp._local(back[-1], True) if back else datetime.combine(debark, dtime(12))
        hours = sum((tp.boundary(w[-1], True) - tp.boundary(w[0])).total_seconds() / 3600
                    for w in (out, back) if w)
        nights = hotel_out + hotel_back
        pto = tp.pto_days(leave, home)
        total = round(cruise_two + flights_two, 2)
        best.append(dict(cruise=cruise, total=total, flights_two=flights_two, how=how, you=you,
                         partner=partner, fares=fares, out=out, back=back, out_note=out_note,
                         back_note=back_note, hotel_nights=nights, pto=pto,
                         travel_hours=round(hours, 1), leave=leave.isoformat(), home=home.isoformat(),
                         voucher=tp._your_voucher(flights, fares, len(out) > 1 or len(back) > 1) if flights else 0.0,
                         score=round(total + PTO_COST * pto + HOUR_COST * hours + HOTEL_EST * nights, 2)))
    best.sort(key=lambda p: p["score"])
    return best[:keep]


def _cruise_pto(sail, debark):
    return tp.pto_days(datetime.combine(sail, dtime(12)), datetime.combine(debark, dtime(12)))


def _prune(ways, now, keep=4):
    """Cheapest few by each fare type and the fastest — enough to find the best pair."""
    if len(ways) <= keep:
        return ways
    inf = float("inf")

    def key(kind):
        def k(w):
            p = tp._price(w[0], now).get(kind)
            return p[0] if p else inf
        return k
    picked = {}
    for k in (key("GoWild"), key("Discount Den"), key("GoWild + Discount Den"),
              lambda w: (tp.boundary(w[0][-1], True) - tp.boundary(w[0][0])).total_seconds(),
              lambda w: (not w[2], key("Discount Den")(w))):  # no-hotel-night ways first
        for w in sorted(ways, key=k)[:keep]:
            picked[id(w)] = w
    return list(picked.values())


# --- Report -------------------------------------------------------------------
REGIONS = [
    ("California (San Francisco / Los Angeles / San Diego)", ("San Francisco", "Los Angeles", "Long Beach", "San Diego")),
    ("Florida (Miami / Fort Lauderdale / Port Canaveral / Tampa / Jacksonville)",
     ("Miami", "Fort Lauderdale", "Port Canaveral", "Tampa", "Jacksonville")),
    ("Gulf (Galveston / New Orleans / Mobile)", ("Galveston", "New Orleans", "Mobile")),
    ("Puerto Rico (San Juan)", ("San Juan",)),
    ("Northeast (Boston / New York)", ("Boston", "New York", "Bayonne")),
]


def _pkg_lines(n, p, now):
    c = p["cruise"]
    sail, debark = date.fromisoformat(c["sail_date"]), date.fromisoformat(c["debark_date"])
    ship = f"{c.get('line', '')} {c.get('ship', '')}".strip()
    per_night = p["total"] / c["nights"]
    lines = [f"{n:>3}. ${p['total']:,.2f} for two (cruise ${2 * c['now']:,} incl. taxes/port fees"
             f" + flights ${p['flights_two']:,.2f}) · ${per_night:,.0f}/night for two"
             f" · plus est. gratuities ~${2 * GRATUITY_EST * c['nights']:,}",
             f"      {ship} · {c['nights']} nights · {tp._fmt(sail)} → {tp._fmt(debark)} · "
             f"{c['from']}" + ("" if c['to'] == c['from'] else f" → {c['to']}")
             + (f" · {c.get('rating', '?')}★ · {c.get('save', '?')}% off · VacationsToGo {c['id']}"
                if c["id"].startswith("#") else f" · price from {c.get('source', 'the cruise line')}")
             + (f" · {c['note']}" if c.get("note") else "")]
    if c.get("rates"):
        lines.append("      Cabins per person: " + ", ".join(f"{k} ${v:,}" for k, v in c["rates"].items())
                     + (f" (the ticker said ${c['ticker_now']:,})" if c.get("ticker_now", c["now"]) != c["now"] else ""))
    if c.get("ports"):
        lines.append(f"      Stops: {', '.join(c['ports'])}")
    if not p["out"] and not p["back"]:
        lines.append(f"      No flights: sails from and returns to the Bay Area. est. PTO {p['pto']}")
        return lines
    extras = [p["how"], f"est. PTO {p['pto']}"]
    if p["hotel_nights"]:
        extras.append(f"{p['hotel_nights']} hotel night{'s' if p['hotel_nights'] > 1 else ''} near the port (not included)")
    if p.get("voucher"):
        extras.append(f"your voucher could cover ≈${p['voucher']:.0f} of your own base fare if booked before it expires")
    lines.append("      " + " · ".join(extras))
    n_out = len(p["out"])
    for label, way, fares, note in (("OUT ", p["out"], p["fares"][:n_out], p["out_note"]),
                                    ("BACK", p["back"], p["fares"][n_out:], p["back_note"])):
        lines += tp._flight_lines(label, way, fares, now) if way else [f"      {label} {note}"]
        if way:
            lines[-1] += f"  [{note}]"
    return lines


def report_lists(packages):
    """[(title, packages)] in report order: overall, value per night, then by region."""
    ranked = sorted(packages, key=lambda p: p["score"])
    lists = [("OVERALL TOP 5 (best score, one per cruise)", ranked[:5]),
             ("BEST VALUE PER NIGHT (top 5)",
              sorted(packages, key=lambda p: p["total"] / p["cruise"]["nights"])[:5])]
    lists += [(title.upper(), [p for p in ranked if any(k in p["cruise"]["from"] for k in keys)][:5])
              for title, keys in REGIONS]
    return lists


def build_report(packages, coverage, now, validation=None):
    out = ["=" * 64, "CRUISE + FRONTIER FLIGHTS — NOVEMBER–DECEMBER 2026", "=" * 64,
           f"Generated {now.astimezone(ZoneInfo('America/Los_Angeles')):%Y-%m-%d %H:%M %Z}. Nothing booked.",
           "Cruise prices: the cheapest cabin on each VacationsToGo deal page (the 90-day ticker's "
           "price if the page couldn't be read), per person, double occupancy (x2 here), "
           "including port charges and government taxes/fees (per VacationsToGo); gratuities extra "
           f"(~${GRATUITY_EST}/person/night shown as an estimate).",
           "Flights: real Frontier fares from SFO/SJC/OAK, landing by ~11:00 on sailing day after the "
           "airport-to-port transfer (or the day before / before 05:00, + hotel night), and leaving after the ship "
           f"docks (~{DOCK:%H:%M}) + {LEAVE_SHIP_BUFFER_H:g} h + transfer. You pay the cheaper of GoWild / "
           "Discount Den per flight; partner Discount Den — or both on Discount Den on one booking.",
           "The $100 voucher only covers YOUR base fare and must be used to book before it expires, "
           "so totals don't assume it. Score = total + $60/PTO day + $5/flight hour + $150/hotel night.",
           "GoWild (base $0.01 + taxes) opens the day before domestic flights and 10 days before San "
           "Juan; fares marked early-booking release are bookable now. A ship won't wait, so only plan "
           "on a not-yet-released GoWild seat with a backup (e.g. fly the day before).", ""]
    for n_list, (title, pool) in enumerate(report_lists(packages)):
        out += ([""] if n_list else []) + [title, "-" * 64]
        out += [line for n, p in enumerate(pool, 1) for line in _pkg_lines(n, p, now)] or ["   (none)"]
    if validation:
        out += ["", "-" * 64, "VALIDATION (final review)"] + validation
    out += ["", "-" * 64, "COVERAGE"] + coverage
    return "\n".join(out) + "\n"


def build_packages(now):
    """(candidates, best package per cruise, cruises with no flights that fit)."""
    cands = with_details(candidates(load_deals()), load_details())
    latest = tp.latest_records(tp.read_jsonl(tp.FLIGHTS))
    flights_by = {k: r["flights"] for k, r in latest.items() if r["status"] == "ok"}
    packages, no_flights = [], []
    for c in cands:
        pk = cruise_packages(c, flights_by, now, keep=1)
        (packages if pk else no_flights).extend(pk or [c])
    return cands, packages, no_flights


def shown_packages(packages):
    """Every package the report lists, once each."""
    return list({p["cruise"]["id"]: p for _, pool in report_lists(packages) for p in pool}.values())


def _package_legs(packages):
    legs = []
    for p in packages:
        for f in p["out"] + p["back"]:
            o, d = tp._ends(f)
            leg = dict(origin=o, destination=d, date=f["legs"][0]["departureDate"][:10])
            if leg not in legs:
                legs.append(leg)
    return legs


def validation_lines(shown, n_legs, packages):
    """How each listed package re-priced after its flight pages were re-fetched."""
    fresh = {p["cruise"]["id"]: p for p in packages}
    flight_ids = lambda p: [tp._flight_id(f) for f in p["out"] + p["back"]]
    lines = [f"Re-fetched {n_legs} Frontier pages behind the {len(shown)} packages listed, "
             "just before this report."]
    for p in shown:
        q, c = fresh.get(p["cruise"]["id"]), p["cruise"]
        name = f"{c['id']} {c.get('ship', '')} {c['sail']}"
        if q is None:
            lines.append(f"  {name}: no Frontier flights fit any more — dropped")
        elif round(q["total"], 2) != round(p["total"], 2) or flight_ids(q) != flight_ids(p):
            lines.append(f"  {name}: ${p['total']:,.2f} → ${q['total']:,.2f}"
                         + ("" if flight_ids(q) == flight_ids(p) else " (different flights now)"))
    if len(lines) == 1:
        lines.append("  Every listed package re-priced the same: all passed.")
    return lines


def make_report(now=None, validate_fetch=None):
    """Build and save the report. With validate_fetch(legs, refresh=True), first
    re-fetch the flights of every listed package and report what changed."""
    now = now or datetime.now(timezone.utc)
    cands, packages, no_flights = build_packages(now)
    validation = None
    if validate_fetch:
        shown = shown_packages(packages)
        legs = _package_legs(shown)
        print(f"Validation: re-checking {len(legs)} legs behind {len(shown)} packages", flush=True)
        validate_fetch(legs, refresh=True)
        now = datetime.now(timezone.utc)
        cands, packages, no_flights = build_packages(now)
        validation = validation_lines(shown, len(legs), packages)
    coverage = [f"Ticker deals: {len(load_deals())}; Nov–Dec, <= {MAX_NIGHTS} nights, reachable ports: {len(cands)}",
                f"Deal pages with cabin prices: {sum(bool(c.get('rates')) for c in cands)} of {len(cands)}; "
                f"cruises with a valid flight plan: {len(packages)}",
                f"Without one (no Frontier flights that fit): {len(no_flights)}"
                + (": " + ", ".join(f"{c['id']} {c['from'][:20]} {c['sail']}" for c in no_flights[:12]) if no_flights else ""),
                f"Data: {OUTPUT} (cruises) and {tp.OUTPUT} (flights)"]
    report = build_report(packages, coverage, now, validation)
    path = OUTPUT / f"report_{now.astimezone():%Y%m%d_%H%M%S}.txt"
    path.write_text(report)
    print(report)
    print(f"💾 Saved report to {path}")
    return report, packages


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=("ticker", "calendars", "flights", "report", "validate", "all"))
    ap.add_argument("--no-email", action="store_true")
    args = ap.parse_args()
    from gowild_deal_report import build_driver

    if args.phase in ("ticker", "all"):
        scrape_ticker(build_driver)
    cands = candidates(load_deals())
    if args.phase in ("calendars", "all"):
        from colombia_trip_search import fetch_calendar

        def fetch(driver, job):
            y, m = map(int, job["month"].split("-"))
            return fetch_calendar(driver, job["origin"], job["destination"], y, m, evidence_dir=None, timeout=35)
        tp.run_jobs(calendar_jobs(cands), tp.CALENDARS, fetch, ("origin", "destination", "month"),
                    ("ok", "no_service", "unverified", "http_error"), ("blocked", "error"))
    if args.phase in ("flights", "all"):
        tp.fetch_flights(flight_jobs(cands))
    if args.phase in ("report", "validate", "all"):
        report, packages = make_report(validate_fetch=tp.fetch_flights if args.phase != "report" else None)
        if not args.no_email:
            from gowild_deal_report import load_env, send_email
            send_email(f"Cruise + Frontier flights — {len(packages)} Nov–Dec packages", report, load_env())


if __name__ == "__main__":
    main()
