#!/usr/bin/env python3
"""Ad-hoc, read-only December 2026 Colombia fare scan; no email or booking.

Use the production browser, preserve complete flight records, and distinguish
empty schedules from failed searches. Do not suppress promotional blackout fares.
"""
import html
import argparse
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from gowild_deal_report import build_driver

OUTPUT = Path(__file__).parent / "results" / "colombia_20260911"
LAUNCHES = {"MDE": date(2026, 12, 10), "BOG": date(2026, 12, 14), "CTG": date(2026, 12, 19)}
END = date(2026, 12, 31)


def model(source):
    for script in BeautifulSoup(source, "html.parser").find_all("script"):
        text = script.string or ""
        if "journeys" not in text or "flights" not in text:
            continue
        text = html.unescape(text)
        try:
            data, _ = json.JSONDecoder().raw_decode(text[text.index("{"):])
        except (ValueError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and "journeys" in data:
            return data
    return None


def search(driver, origin, dest, day):
    url = "https://booking.flyfrontier.com/Flight/InternalSelect?" + urlencode(
        dict(o1=origin, d1=dest, dd1=day.strftime("%b %d, %Y"), ADT=1, mon="true", promo="")
    )
    record = dict(origin=origin, destination=dest, date=day.isoformat(), url=url,
                  checked_at=datetime.now().astimezone().isoformat())
    # Navigate in the normal browser without waiting for unrelated ad resources.
    driver.execute_cdp_cmd("Page.navigate", {"url": url})
    deadline = time.monotonic() + 40
    data = None
    while time.monotonic() < deadline:
        time.sleep(1)
        source = driver.page_source
        if "HTTP ERROR 406" in source or "ERR_HTTP_RESPONSE_CODE_FAILURE" in source:
            record.update(status="http_error", flights=[], title=driver.title)
            return record
        candidate = model(source)
        if candidate and candidate.get("originOne") == origin and candidate.get("destinationOne") == dest and str(candidate.get("departureDateOne", ""))[:10] == day.isoformat():
            data = candidate
            break
        if "px-captcha" in source:
            record.update(status="blocked", flights=[])
            return record
    if data is None:
        record.update(status="unverified", flights=[], title=driver.title)
        return record
    flights = [f for j in data.get("journeys") or [] for f in j.get("flights") or []]
    # Check the actual itinerary as well as the requested page's date and route.
    flights = [f for f in flights if f.get("legs") and
               f["legs"][0].get("departureStation") == origin and
               f["legs"][-1].get("arrivalStation") == dest and
               f["legs"][0].get("departureDate", "")[:10] == day.isoformat()]
    record.update(status="ok", flights=flights,
                  isGoWildOutOfRange=data.get("isGoWildOutOfRange"))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", choices=("MCO", "SFO", "both"), default="both")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "searches.jsonl"
    done = set()
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r["status"] == "ok":
                done.add((r["origin"], r["destination"], r["date"]))
    jobs = []
    # Check the international bottleneck, then every end-to-end SFO route.
    for home in (("MCO", "SFO") if args.home == "both" else (args.home,)):
        for dest, launch in LAUNCHES.items():
            for origin, arrival in ((home, dest), (dest, home)):
                day = launch - timedelta(days=1) if origin == "SFO" else launch
                while day <= END:
                    jobs.append((origin, arrival, day))
                    day += timedelta(days=1)
    # Domestic control proves this same public session can display GoWild fares.
    jobs.insert(0, ("SFO", "MCO", date(2026, 12, 9)))
    driver = build_driver()
    failures = 0
    try:
        driver.set_page_load_timeout(45)
        driver.get("https://www.flyfrontier.com/")
        time.sleep(5)
        for index, (origin, dest, day) in enumerate(jobs, 1):
            if (origin, dest, day.isoformat()) in done:
                continue
            try:
                r = search(driver, origin, dest, day)
            except Exception as exc:
                r = dict(origin=origin, destination=dest, date=day.isoformat(),
                         status="error", error=type(exc).__name__, flights=[])
            with path.open("a") as out:
                out.write(json.dumps(r) + "\n")
            gw = [f for f in r["flights"] if f.get("isGoWildFareEnabled") and (f.get("goWildFare") or 0) > 0]
            print(f"[{index}/{len(jobs)}] {origin}-{dest} {day}: {r['status']}, {len(r['flights'])} flights, {len(gw)} GoWild", flush=True)
            failures = failures + 1 if r["status"] != "ok" else 0
            if failures >= 3:
                print("Stopping after three unsuccessful pages; resume to retry.", flush=True)
                break
            time.sleep(3)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
