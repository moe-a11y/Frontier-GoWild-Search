#!/usr/bin/env python3
"""
Short-lived watch: cheapest GoWild fare SFO/SJC -> BUF (one way) on Sep 17/18/19, 2026.

Runs on its own launchd job (com.frontier.bufwatch), separate from the regular
deal checker: 00:01 and 10:01 daily, Mon Sep 14 through Thu Sep 17 00:01.
Each run searches the three dates, emails the cheapest GoWild fare found, and
notes how it moved since the previous run.

The job is inert after WATCH_ENDS even if launchd fires it again (the calendar
entries are month/day only, so they would recur next September).

    python3 buf_watch.py [--dry-run]   # dry run: no email, baseline untouched
"""

import argparse
import json
import os
import time
from datetime import date, datetime

from gowild_deal_report import (
    BASE_DIR,
    _seats_left,
    build_driver,
    extract_deals,
    load_env,
    parse_flights,
    send_email,
)

ORIGINS = ["SFO", "SJC"]
DEST = "BUF"
DEST_NAME = "Buffalo, NY"
DATES = ["2026-09-17", "2026-09-18", "2026-09-19"]
WATCH_ENDS = date(2026, 9, 17)
PAGE_WAIT = 9
BETWEEN_REQUESTS = 5
LAST_PATH = os.path.join(BASE_DIR, "results", "bufwatch_last.json")


def search_date(driver, origin, date_iso):
    """Return (deals, flight_count, blocked, driver) for one origin/date.

    On a dead session or PerimeterX block, retries once in a fresh *headful*
    browser (visible window — gets past PerimeterX more reliably than headless).
    The caller keeps the returned driver for the remaining searches."""
    display = datetime.strptime(date_iso, "%Y-%m-%d").strftime("%b %-d, %Y")
    url = (
        f"https://booking.flyfrontier.com/Flight/InternalSelect?"
        f"o1={origin}&d1={DEST}&dd1={display.replace(' ', '%20')}"
        f"&ADT=1&mon=true&promo="
    )
    for attempt in (1, 2):
        try:
            driver.get(url)
            time.sleep(PAGE_WAIT)
            source = driver.page_source
            if "px-captcha" in source:
                raise RuntimeError("PerimeterX block")
            flights = parse_flights(source)
            deals = extract_deals(flights, origin, DEST, DEST_NAME, display, False)
            return deals, len(flights), False, driver
        except Exception as e:
            print(f"    attempt {attempt}: {type(e).__name__}: {e}")
            if attempt == 2:
                return [], 0, True, driver
            try:
                driver.quit()
            except Exception:
                pass
            driver = build_driver(headless=False)
            driver.get("https://www.flyfrontier.com/")
            time.sleep(5)


def _fmt(d):
    bits = [d["stops"], d["duration"], f"Departs {d['departs']}"]
    seats = _seats_left(d.get("seats"))
    if d["type"] == "GoWild" and seats is not None:
        bits.append(f"{seats} seats left")
    return f"${d['price']:.2f}  —  " + " | ".join(bits)


def load_last():
    try:
        with open(LAST_PATH) as f:
            return json.load(f)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="search and print only: no email, baseline not updated")
    args = ap.parse_args()

    now = datetime.now()
    if now.date() > WATCH_ENDS:
        print(f"Watch ended {WATCH_ENDS}; nothing to do.")
        return

    dates = [d for d in DATES if d >= now.strftime("%Y-%m-%d")]
    print(f"{'/'.join(ORIGINS)}→BUF GoWild watch  |  {now:%Y-%m-%d %H:%M}  |  dates: {', '.join(dates)}")

    results = {}
    driver = build_driver()
    try:
        driver.get("https://www.flyfrontier.com/")
        time.sleep(5)
        for d in dates:
            for origin in ORIGINS:
                print(f"  {origin}→{DEST} {d}...", end=" ", flush=True)
                deals, n, blocked, driver = search_date(driver, origin, d)
                results[(origin, d)] = {"deals": deals, "flights": n, "blocked": blocked}
                gw = sum(1 for x in deals if x["type"] == "GoWild")
                print("BLOCKED" if blocked else f"{n} flights (GW:{gw})")
                time.sleep(BETWEEN_REQUESTS)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    gowild = [x for r in results.values() for x in r["deals"] if x["type"] == "GoWild"]
    best = min(gowild, key=lambda x: x["price"]) if gowild else None
    last = load_last()

    n_blocked = sum(1 for r in results.values() if r["blocked"])
    all_blocked = n_blocked == len(results)

    # Movement vs the previous run — only meaningful when every search ran.
    if n_blocked:
        move = None
    elif best and last and last.get("price") is not None:
        diff = best["price"] - last["price"]
        move = (
            "no change" if abs(diff) < 0.01
            else f"{'down' if diff < 0 else 'up'} ${abs(diff):.2f} from ${last['price']:.2f}"
        )
    elif best and last:
        move = "newly available (none last run)"
    elif not best and last and last.get("price") is not None:
        move = f"gone — was ${last['price']:.2f} last run"
    else:
        move = None

    out = ["=" * 50, f"{' / '.join(ORIGINS)} → BUFFALO  ·  GOWILD WATCH (one way)", "=" * 50, ""]
    if all_blocked:
        out.append("NO DATA THIS RUN: every search was blocked by Frontier's bot check")
    elif best:
        out.append(f"CHEAPEST GOWILD: ${best['price']:.2f} from {best['origin']} on {best['flight_date']}")
        out.append(f"   {_fmt(best)}")
    else:
        out.append("CHEAPEST GOWILD: none available on Sep 17–19 right now")
    if move:
        out.append(f"   ({move})")
    if n_blocked and not all_blocked:
        out.append(f"   ⚠️  {n_blocked} of {len(results)} searches were blocked — result may be incomplete")

    for d in dates:
        label = datetime.strptime(d, "%Y-%m-%d").strftime("%a %b %-d")
        out.append(f"\n{label}")
        out.append("-" * 40)
        for origin in ORIGINS:
            r = results[(origin, d)]
            out.append(f"  From {origin}:")
            if r["blocked"]:
                out.append("   search blocked by Frontier's bot check — no data this run")
                continue
            if not r["flights"]:
                out.append("   no Frontier flights listed")
                continue
            gw = sorted((x for x in r["deals"] if x["type"] == "GoWild"), key=lambda x: x["price"])
            dd = sorted((x for x in r["deals"] if x["type"] == "Discount Den"), key=lambda x: x["price"])
            if gw:
                for x in gw:
                    out.append(f"   GoWild        {_fmt(x)}")
            else:
                out.append(f"   GoWild        none ({r['flights']} flights listed)")
            if dd:
                out.append(f"   Discount Den  {_fmt(dd[0])}   (cheapest, for reference)")

    out.append("\n" + "-" * 40)
    out.append(f"Generated: {now:%Y-%m-%d %H:%M} PT")
    out.append("Watch runs 00:01 + 10:01 daily through Thu Sep 17 00:01.")
    report = "\n".join(out)
    print("\n" + report)

    os.makedirs(os.path.dirname(LAST_PATH), exist_ok=True)
    with open(os.path.join(BASE_DIR, "results", f"bufwatch_{now:%Y%m%d_%H%M}.txt"), "w") as f:
        f.write(report)
    # Only overwrite the baseline when every date was actually searched, so a
    # blocked run doesn't read as "fare gone" next time.
    if not args.dry_run and not any(r["blocked"] for r in results.values()):
        with open(LAST_PATH, "w") as f:
            json.dump({"price": best["price"] if best else None,
                       "date": best["flight_date"] if best else None,
                       "origin": best["origin"] if best else None,
                       "checked": now.isoformat()}, f)

    if not args.dry_run:
        if all_blocked:
            subject = f"{'/'.join(ORIGINS)}→BUF watch: searches blocked — no data this run"
        elif best:
            subject = f"{best['origin']}→BUF GoWild: ${best['price']:.2f} on {best['flight_date'].rsplit(',', 1)[0]}"
        else:
            subject = f"{'/'.join(ORIGINS)}→BUF GoWild: none available (Sep 17–19)"
        if move:
            subject += f" ({move})"
        if n_blocked and not all_blocked:
            subject += f" — {n_blocked} searches blocked"
        send_email(subject, report, load_env())


if __name__ == "__main__":
    main()
