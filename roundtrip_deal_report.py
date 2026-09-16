#!/usr/bin/env python3
"""
Ad-hoc ROUND TRIP Frontier deal checker + emailer.

Same origins/destinations/email as the scheduled one-way checker
(`gowild_deal_report.py`), but searches a set of outbound dates and a set of
return dates, then pairs them into round trips ranked by total price.

    python3 roundtrip_deal_report.py --out 2026-09-03,2026-09-04 \
                                     --back 2026-09-07,2026-09-08

Blackout dates are NOT skipped here: GoWild is unavailable on them but Discount
Den is not, so the date is still searched and GoWild fares are dropped for that
date (and the report says so).
"""

import argparse
import os
import time
from datetime import datetime

from config import (
    DOMESTIC_DESTINATIONS,
    INTERNATIONAL_DESTINATIONS,
    ORIGINS,
    is_blackout_date,
)
from gowild_deal_report import (
    BASE_DIR,
    MAX_DRIVER_RESTARTS,
    MIN_OTHER_DESTS,
    OVERSERVED_DESTS,
    _restart_driver,
    _seats_left,
    _short_name,
    build_driver,
    extract_deals,
    load_env,
    parse_flights,
    send_email,
)

PAGE_WAIT = int(os.environ.get("DEAL_PAGE_WAIT", "8"))
BETWEEN_REQUESTS = int(os.environ.get("DEAL_BETWEEN", "4"))
ALL_DESTINATIONS = {**INTERNATIONAL_DESTINATIONS, **DOMESTIC_DESTINATIONS}


def _fetch(driver, url):
    driver.get(url)
    time.sleep(PAGE_WAIT)
    return parse_flights(driver.page_source)


def search_leg(driver, origin, dest, dest_code, dest_name, date_iso, is_intl):
    """Fetch one origin->dest date and return its deals (GoWild dropped on blackouts)."""
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    display = dt.strftime("%b %-d, %Y")
    url = (
        f"https://booking.flyfrontier.com/Flight/InternalSelect?"
        f"o1={origin}&d1={dest}&dd1={display.replace(' ', '%20')}"
        f"&ADT=1&mon=true&promo="
    )
    flights = _fetch(driver, url)
    deals = extract_deals(flights, origin, dest, dest_name, display, is_intl)
    if is_blackout_date(date_iso):
        deals = [d for d in deals if d["type"] != "GoWild"]
    for d in deals:
        d["date_iso"] = date_iso
        d["dest_code"] = dest_code  # the non-Bay-Area end of the leg
    return deals, len(flights)


def search_all(driver, out_dates, back_dates):
    """Scan every origin x destination x date, both directions.

    Returns (outbound_deals, return_deals, legs_checked, driver).
    """
    outbound, returning = [], []
    legs = 0
    consecutive_restarts = 0

    jobs = []
    for dest_code, dest_name in ALL_DESTINATIONS.items():
        is_intl = dest_code in INTERNATIONAL_DESTINATIONS
        for origin in ORIGINS:
            for d in out_dates:
                jobs.append(("out", origin, dest_code, dest_code, dest_name, d, is_intl))
            for d in back_dates:
                jobs.append(("back", dest_code, origin, dest_code, dest_name, d, is_intl))

    for direction, frm, to, dest_code, dest_name, date_iso, is_intl in jobs:
        legs += 1
        arrow = "→"
        print(
            f"  [{legs}/{len(jobs)}] {direction:<4} {frm}{arrow}{to} {date_iso}...",
            end=" ",
            flush=True,
        )
        try:
            try:
                deals, n = search_leg(
                    driver, frm, to, dest_code, dest_name, date_iso, is_intl
                )
            except Exception as e:
                if consecutive_restarts >= MAX_DRIVER_RESTARTS:
                    raise
                consecutive_restarts += 1
                print(
                    f"{type(e).__name__}; restarting Chrome "
                    f"({consecutive_restarts}/{MAX_DRIVER_RESTARTS})...",
                    end=" ",
                    flush=True,
                )
                driver = _restart_driver(driver)
                deals, n = search_leg(
                    driver, frm, to, dest_code, dest_name, date_iso, is_intl
                )
            (outbound if direction == "out" else returning).extend(deals)
            gw = sum(1 for d in deals if d["type"] == "GoWild")
            dd = sum(1 for d in deals if d["type"] == "Discount Den")
            print(f"{n} flights (GW:{gw} DD:{dd})")
            consecutive_restarts = 0
        except Exception as e:
            print(f"error: {type(e).__name__}")
        time.sleep(BETWEEN_REQUESTS)

    return outbound, returning, legs, driver


def build_roundtrips(outbound, returning):
    """Pair each outbound leg with each return leg of the same destination and
    fare type; keep the cheapest pairing per (destination, type, date pair)."""
    best = {}
    for o in outbound:
        for r in returning:
            if o["dest_code"] != r["dest_code"] or o["type"] != r["type"]:
                continue
            if r["date_iso"] <= o["date_iso"]:
                continue  # return must be after departure
            total = o["price"] + r["price"]
            key = (o["dest_code"], o["type"], o["date_iso"], r["date_iso"])
            if key not in best or total < best[key]["total"]:
                best[key] = {
                    "dest": o["dest_code"],
                    "dest_name": o["dest_name"],
                    "type": o["type"],
                    "is_intl": o["is_intl"],
                    "total": total,
                    "out": o,
                    "back": r,
                }
    return list(best.values())


def _top_roundtrips(trips, n=10):
    """Cheapest n, reserving MIN_OTHER_DESTS slots for non-LAS/SLC/DEN destinations."""
    ranked = sorted(trips, key=lambda t: t["total"])
    others = [t for t in ranked if t["dest"] not in OVERSERVED_DESTS]
    picked = others[:MIN_OTHER_DESTS]
    seen = {id(t) for t in picked}
    for t in ranked:
        if len(picked) >= n:
            break
        if id(t) not in seen:
            picked.append(t)
            seen.add(id(t))
    return sorted(picked, key=lambda t: t["total"])


def _leg_line(label, leg, home_side):
    seats = _seats_left(leg.get("seats")) if leg["type"] == "GoWild" else None
    route = f"{leg['origin']}→{leg['dest']}"
    bits = [leg.get("stops", "N/A"), leg.get("duration", "N/A"), f"Departs {leg['departs']}"]
    if seats is not None:
        bits.append(f"{seats} seats left")
    return (
        f"      {label} {leg['flight_date']} · {route} · ${leg['price']:.2f}\n"
        f"           {' | '.join(bits)}"
    )


def _trip_lines(t, rank, tag=""):
    city = _short_name(t["dest_name"])
    o, r = t["out"], t["back"]
    same = "" if o["origin"] == r["dest"] else "  [open-jaw: returns to a different Bay Area airport]"
    header = (
        f"{rank:>4}. {o['origin']} ⇄ {t['dest']} ({city}) — "
        f"${t['total']:.2f} round trip"
    )
    if tag:
        header += f"  [{tag}]"
    header += same
    return "\n".join([header, _leg_line("OUT ", o, True), _leg_line("BACK", r, False)])


def build_report(trips, outbound, returning, meta):
    gowild = _top_roundtrips([t for t in trips if t["type"] == "GoWild"])
    discden = _top_roundtrips([t for t in trips if t["type"] == "Discount Den"])
    intl_gw = sorted(
        (t for t in trips if t["is_intl"] and t["type"] == "GoWild"),
        key=lambda t: t["total"],
    )
    intl_dd = sorted(
        (t for t in trips if t["is_intl"] and t["type"] == "Discount Den"),
        key=lambda t: t["total"],
    )
    intl = (intl_gw + intl_dd)[:5]

    out = []
    out.append("=" * 50)
    out.append("FRONTIER ROUND TRIP DEAL REPORT")
    out.append(f"Out: {meta['out_dates']}   Back: {meta['back_dates']}")
    out.append("=" * 50)

    if meta["blackout_note"] != "None":
        out.append("")
        out.append("⚠️  GOWILD BLACKOUT: " + meta["blackout_note"])
        out.append("    GoWild fares are not offered on those dates, so they were")
        out.append("    excluded for them. Discount Den fares are unaffected.")

    out.append("\n\nTOP 10 GOWILD ROUND TRIPS")
    out.append("-" * 40)
    if gowild:
        for i, t in enumerate(gowild, 1):
            out.append(_trip_lines(t, i) + "\n")
    else:
        out.append("   (none found)\n")

    out.append("\nTOP 10 DISCOUNT DEN ROUND TRIPS")
    out.append("-" * 40)
    if discden:
        for i, t in enumerate(discden, 1):
            out.append(_trip_lines(t, i) + "\n")
    else:
        out.append("   (none found)\n")

    out.append("\nTOP 5 INTERNATIONAL / NON-CONUS ROUND TRIPS")
    out.append("-" * 40)
    if intl:
        for i, t in enumerate(intl, 1):
            out.append(_trip_lines(t, i, tag=t["type"]) + "\n")
    else:
        out.append("   (none found)\n")

    out.append("\n" + "-" * 40)
    out.append(f"Outbound dates:     {meta['out_dates']}")
    out.append(f"Return dates:       {meta['back_dates']}")
    out.append(f"Origins:            {', '.join(ORIGINS)}")
    out.append(f"Destinations:       {len(ALL_DESTINATIONS)}")
    out.append(f"Legs checked:       {meta['legs']}")
    out.append(f"One-way fares found: {len(outbound)} outbound, {len(returning)} return")
    out.append(f"Round trips built:  {len(trips)}")
    out.append(f"Blackout dates:     {meta['blackout_note']}")
    out.append(f"Generated:          {meta['generated']}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="2026-09-03,2026-09-04")
    ap.add_argument("--back", default="2026-09-07,2026-09-08")
    ap.add_argument("--no-email", action="store_true")
    args = ap.parse_args()

    out_dates = [d.strip() for d in args.out.split(",") if d.strip()]
    back_dates = [d.strip() for d in args.back.split(",") if d.strip()]
    now = datetime.now()

    fmt = lambda ds: ", ".join(
        datetime.strptime(d, "%Y-%m-%d").strftime("%a %b %-d") for d in ds
    )
    blackouts = [d for d in out_dates + back_dates if is_blackout_date(d)]
    blackout_note = fmt(blackouts) if blackouts else "None"

    print("=" * 60)
    print("FRONTIER ROUND TRIP DEAL CHECKER")
    print(f"  Outbound: {fmt(out_dates)}")
    print(f"  Return:   {fmt(back_dates)}")
    print(f"  Origins: {', '.join(ORIGINS)}  |  {len(ALL_DESTINATIONS)} destinations")
    print(f"  GoWild blackout dates in range: {blackout_note}")
    print("=" * 60)

    driver = build_driver()
    outbound, returning, legs = [], [], 0
    try:
        driver.get("https://www.flyfrontier.com/")
        time.sleep(5)
        outbound, returning, legs, driver = search_all(driver, out_dates, back_dates)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    trips = build_roundtrips(outbound, returning)
    meta = {
        "out_dates": fmt(out_dates),
        "back_dates": fmt(back_dates),
        "legs": legs,
        "blackout_note": blackout_note,
        "generated": now.strftime("%Y-%m-%d %H:%M:%S PT"),
    }
    report = build_report(trips, outbound, returning, meta)
    print("\n" + report)

    results_dir = os.path.join(BASE_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)
    path = os.path.join(
        results_dir, f"roundtrip_report_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    )
    with open(path, "w") as f:
        f.write(report)
    print(f"\n💾 Saved report to {path}")

    if not args.no_email:
        subject = (
            f"Frontier Round Trips — {len(trips)} options "
            f"({fmt(out_dates)} → {fmt(back_dates)})"
        )
        send_email(subject, report, load_env())


if __name__ == "__main__":
    main()
