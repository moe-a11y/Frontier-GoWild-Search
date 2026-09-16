#!/usr/bin/env python3
"""Collect month calendars and validate shortlisted Colombia flight dates.

Calendar prices are rounded screening prices, never final itinerary quotes.
This script only searches; emailing is a separate explicit action.
"""
import argparse
import calendar
import json
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from colombia_search import search
from gowild_deal_report import build_driver

OUTPUT = Path(__file__).parent / "results" / "colombia_expanded"
MONTHS = [(2026, 12), (2027, 2), (2027, 3)]
CITIES = ("MDE", "BOG", "CTG")


def parse_calendar(source, origin, dest, year, month):
    soup = BeautifulSoup(source, "html.parser")
    marker = 'nca.createObject("CalendarAndLowFareSelectSwitcher", '
    config = None
    for tag in soup.find_all("script"):
        text = tag.string or ""
        if marker in text:
            config, _ = json.JSONDecoder().raw_decode(text.split(marker, 1)[1])
            break
    if not config or config.get("origin") != origin or config.get("destination") != dest:
        return None
    selected = [x for x in soup.select(".ibe-flight-slider-box-selected") if x.get("data-key")]
    if len(selected) != 1 or f"dd1={year}-{month:02d}" not in selected[0]["data-key"]:
        return None
    days = []
    for cell in soup.select(".ibe-calendar-item"):
        day = cell.select_one(".calendar-date")
        if not day or not day.get_text(strip=True).isdigit():
            continue
        price = cell.select_one(".calendar-price")
        text = price.get_text(strip=True).replace("$", "").replace(",", "") if price else ""
        days.append(dict(date=date(year, month, int(day.text)).isoformat(),
                         available="calendar-active-day" in cell.get("class", []),
                         is_discount_den=cell.get("data-isdd") == "true",
                         calendar_price=float(text) if text else None))
    if len(days) != calendar.monthrange(year, month)[1] or len({d["date"] for d in days}) != len(days):
        return None
    return days


def fetch_calendar(driver, origin, dest, year, month):
    url = "https://booking.flyfrontier.com/Flight/InternalSelect?" + urlencode(
        dict(o1=origin, d1=dest, dd1=f"{year}-{month:02d}-15", ADT=1, mon="true", promo="", c="true")
    )
    record = dict(origin=origin, destination=dest, month=f"{year}-{month:02d}",
                  checked_at=datetime.now().astimezone().isoformat(), url=url)
    driver.execute_cdp_cmd("Page.navigate", {"url": url})
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        time.sleep(2)
        source = driver.page_source
        if "HTTP ERROR 406" in source or "px-captcha" in source:
            return dict(record, status="blocked", days=[])
        days = parse_calendar(source, origin, dest, year, month)
        if days is not None:
            name = f"calendar_{origin}_{dest}_{year}_{month:02d}.html"
            (OUTPUT / name).write_text(source)
            return dict(record, status="ok", days=days, evidence=name)
    return dict(record, status="unverified", days=[], title=driver.title)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("calendars", "flights"))
    parser.add_argument("--jobs", type=Path)
    parser.add_argument("--refresh", action="store_true", help="Recheck successful dates in the supplied jobs")
    args = parser.parse_args()
    if args.phase == "flights" and args.jobs is None:
        parser.error("flights requires --jobs with a list of route/date requests")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / (args.phase + ".jsonl")
    key_fields = ("origin", "destination", "month" if args.phase == "calendars" else "date")
    done = set()
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r["status"] == "ok":
                done.add(tuple(r[k] for k in key_fields))
    if args.jobs:
        jobs = json.loads(args.jobs.read_text())
    else:
        jobs = []
        for year, month in MONTHS:
            for city in CITIES:
                for origin, dest in (("MCO", city), (city, "MCO")):
                    jobs.append(dict(origin=origin, destination=dest, month=f"{year}-{month:02d}"))
            for origin, dest in (("SFO", "MCO"), ("MCO", "SFO")):
                jobs.append(dict(origin=origin, destination=dest, month=f"{year}-{month:02d}"))
    driver = build_driver()
    failures = 0
    try:
        driver.set_page_load_timeout(45)
        driver.get("https://www.flyfrontier.com/")
        time.sleep(5)
        for index, job in enumerate(jobs, 1):
            key = tuple(job[k] for k in key_fields)
            if key in done and not args.refresh:
                continue
            try:
                if args.phase == "calendars":
                    year, month = map(int, job["month"].split("-"))
                    r = fetch_calendar(driver, job["origin"], job["destination"], year, month)
                    detail = f"{sum(d['available'] for d in r['days'])} available dates"
                else:
                    r = search(driver, job["origin"], job["destination"], date.fromisoformat(job["date"]))
                    gw = sum(f.get("isGoWildFareEnabled") and (f.get("goWildFare") or 0) > 0 for f in r["flights"])
                    detail = f"{len(r['flights'])} flights, {gw} GoWild"
            except Exception as exc:
                r = dict(job, status="error", error=type(exc).__name__)
                detail = type(exc).__name__
            with path.open("a") as out:
                out.write(json.dumps(r) + "\n")
            print(f"[{index}/{len(jobs)}] {' '.join(key)}: {r['status']}, {detail}", flush=True)
            failures = 0 if r["status"] == "ok" else failures + 1
            if failures >= 3:
                print("Stopped after three unsuccessful requests.", flush=True)
                break
            time.sleep(12)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
