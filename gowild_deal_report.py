#!/usr/bin/env python3
"""
Scheduled Frontier deal checker + emailer.

Runs unattended (intended: Tue/Wed/Thu 00:01 local via launchd). For each origin
in config.ORIGINS it checks:
  - Domestic (CONUS) destinations for the NEXT day
  - International / non-CONUS destinations for 10 days out
...collecting BOTH GoWild fares and Discount Den fares. It then builds a report of
the Top 10 GoWild deals, Top 10 Discount Den deals, and Top 5 international deals
(cheapest first) and emails it.

Blackout dates (config.GOWILD_BLACKOUT_DATES) are skipped automatically: GoWild is
not offered on those days, so that date's group is not searched.

Email credentials are read from a local `.env` file (gitignored) or real env vars:
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=465
    SMTP_USER=you@gmail.com
    SMTP_PASSWORD=your_gmail_app_password   # NOT your normal password
    EMAIL_FROM=you@gmail.com                # optional, defaults to SMTP_USER
    EMAIL_TO=muhammadalinajfi1@gmail.com    # optional, has a default below

If credentials are missing the report is still printed and saved to results/, just
not emailed.
"""

import html as html_lib
import json
import os
import re
import shutil
import smtplib
import subprocess
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

from config import (
    DOMESTIC_DESTINATIONS,
    INTERNATIONAL_DESTINATIONS,
    ORIGINS,
    is_blackout_date,
)

# --- Settings -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EMAIL_TO = "muhammadalinajfi1@gmail.com"
# Run the browser without a visible window. Headful is more reliable against
# PerimeterX, but a scheduled 00:01 job usually wants no window -> default headless.
HEADLESS = os.environ.get("DEAL_HEADLESS", "1") == "1"
PAGE_WAIT = 9          # seconds to let each results page load
BETWEEN_REQUESTS = 5   # extra polite delay between routes


# --- Browser --------------------------------------------------------------
def build_driver(headless=None):
    """Arch-safe undetected Chrome driver (see gowild_WORKING.build_driver)."""
    if headless is None:
        headless = HEADLESS
    from selenium.webdriver.common.selenium_manager import SeleniumManager

    paths = SeleniumManager().binary_paths(["--browser", "chrome"])
    driver_path = paths["driver_path"]

    version_main = None
    try:
        out = subprocess.run(
            [paths["browser_path"], "--version"], capture_output=True, text=True
        )
        version_main = int(out.stdout.strip().split()[-1].split(".")[0])
    except Exception:
        version_main = None

    signed = driver_path + "_uc_signed"
    if not os.path.exists(signed):
        shutil.copy2(driver_path, signed)
        os.chmod(signed, 0o755)
        subprocess.run(["codesign", "--force", "--sign", "-", signed], check=False)

    uc.Patcher.auto = lambda self, *a, **k: None

    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1400,1000")
    return uc.Chrome(
        options=options,
        use_subprocess=True,
        driver_executable_path=signed,
        version_main=version_main,
    )


# --- Parsing --------------------------------------------------------------
def parse_flights(page_source):
    """Return the list of flight dicts from a results page, or [] if none/blocked."""
    if "px-captcha" in page_source:
        return []
    soup = BeautifulSoup(page_source, "html.parser")
    for script in soup.find_all("script"):
        t = script.string
        if t and "journeys" in t and "flights" in t:
            decoded = html_lib.unescape(t)
            start = decoded.find("{")
            if start == -1:
                continue
            depth = 0
            end = start
            for i in range(start, len(decoded)):
                if decoded[i] == "{":
                    depth += 1
                elif decoded[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            try:
                data = json.loads(decoded[start:end])
            except json.JSONDecodeError:
                continue
            if "journeys" in data and data["journeys"]:
                return data["journeys"][0].get("flights") or []
    return []


def _departs(flight):
    try:
        return flight.get("legs", [{}])[0].get("departureDateFormatted") or "N/A"
    except (IndexError, AttributeError):
        return "N/A"


def extract_deals(flights, origin, dest, dest_name, flight_date_display, is_intl):
    """Pull GoWild and Discount Den deals out of a route's flight list."""
    deals = []
    for f in flights:
        stops = f.get("stopsText", "N/A")
        duration = f.get("duration", "N/A")
        departs = _departs(f)

        # GoWild
        gw = f.get("goWildFare")
        if f.get("isGoWildFareEnabled") and gw is not None and gw > 0:
            deals.append(
                {
                    "type": "GoWild",
                    "origin": origin,
                    "dest": dest,
                    "dest_name": dest_name,
                    "price": float(gw),
                    "stops": stops,
                    "duration": duration,
                    "departs": departs,
                    "seats": f.get("goWildFareSeatsRemaining"),
                    "flight_date": flight_date_display,
                    "is_intl": is_intl,
                }
            )

        # Discount Den
        dd = f.get("discountDenFare")
        if dd is not None and dd > 0:
            deals.append(
                {
                    "type": "Discount Den",
                    "origin": origin,
                    "dest": dest,
                    "dest_name": dest_name,
                    "price": float(dd),
                    "stops": stops,
                    "duration": duration,
                    "departs": departs,
                    "seats": f.get("discountDenFareSeatsRemaining"),
                    "flight_date": flight_date_display,
                    "is_intl": is_intl,
                }
            )
    return deals


# --- Report formatting ----------------------------------------------------
def _short_name(name):
    return name.split(",")[0].strip()


def _seats_left(val):
    """Frontier returns seats remaining as an int or as text ("2 Seats Left!")."""
    if isinstance(val, (int, float)):
        return int(val)
    m = re.search(r"\d+", str(val or ""))
    return int(m.group()) if m else None


def _deal_lines(deal, rank, tag=""):
    city = _short_name(deal["dest_name"])
    header = f"{rank:>4}. {deal['origin']} > {deal['dest']} ({city}) — ${deal['price']:.2f}"
    if tag:
        header += f"  [{tag}]"
    detail = f"      {deal['stops']} | {deal['duration']} | Departs {deal['departs']}"
    seats = _seats_left(deal.get("seats")) if deal["type"] == "GoWild" else None
    if seats is not None:
        detail += f" | {seats} seats left"
    date_line = f"      Flight date: {deal['flight_date']}"
    return "\n".join([header, detail, date_line])


OVERSERVED_DESTS = {"LAS", "SLC", "DEN"}  # cap these in the top-10 lists
MIN_OTHER_DESTS = 5  # each top-10 must carry at least this many other destinations


def _top_deals(deals, n=10):
    """Cheapest `n` deals, but reserve at least MIN_OTHER_DESTS slots for
    destinations outside OVERSERVED_DESTS. Only when there aren't that many
    non-LAS/SLC/DEN deals may those three fill more than n - MIN_OTHER_DESTS
    slots."""
    ranked = sorted(deals, key=lambda d: d["price"])
    others = [d for d in ranked if d["dest"] not in OVERSERVED_DESTS]
    picked = others[:MIN_OTHER_DESTS]
    picked_ids = {id(d) for d in picked}
    for d in ranked:
        if len(picked) >= n:
            break
        if id(d) not in picked_ids:
            picked.append(d)
            picked_ids.add(id(d))
    return sorted(picked, key=lambda d: d["price"])


def build_report(deals, meta, cruise_section=None):
    by_price = lambda d: d["price"]
    gowild = _top_deals([d for d in deals if d["type"] == "GoWild"])
    discden = _top_deals([d for d in deals if d["type"] == "Discount Den"])
    intl = sorted((d for d in deals if d["is_intl"]), key=by_price)[:5]

    out = []
    out.append("=" * 50)
    out.append("GOWILD & DISCOUNT DEN DEAL REPORT")
    out.append("=" * 50)

    out.append("\nTOP 10 GOWILD DEALS")
    out.append("-" * 40)
    if gowild:
        for i, d in enumerate(gowild, 1):
            out.append(_deal_lines(d, i) + "\n")
    else:
        out.append("   (none found)\n")

    out.append("\nTOP 10 DISCOUNT DEN DEALS")
    out.append("-" * 40)
    if discden:
        for i, d in enumerate(discden, 1):
            out.append(_deal_lines(d, i) + "\n")
    else:
        out.append("   (none found)\n")

    out.append("\nTOP 5 INTERNATIONAL / NON-CONUS DEALS")
    out.append("-" * 40)
    if intl:
        for i, d in enumerate(intl, 1):
            tag = "GoWild" if d["type"] == "GoWild" else "Discount Den"
            out.append(_deal_lines(d, i, tag=tag) + "\n")
    else:
        out.append("   (none found)\n")

    if cruise_section:
        out.append("\n" + cruise_section)

    out.append("\n" + "-" * 40)
    out.append(f"CONUS search date:  {meta['conus_date']}")
    out.append(f"Int'l search date:  {meta['intl_date']}")
    out.append(f"Origins:            {', '.join(ORIGINS)}")
    out.append(f"Destinations checked:       {meta['routes_checked']}")
    out.append(f"Blackout skipped:   {meta['blackout_note']}")
    out.append(f"Generated:          {meta['generated']}")
    return "\n".join(out)


# --- Email ----------------------------------------------------------------
def load_env():
    """Load KEY=VALUE lines from .env (real env vars take precedence)."""
    env = {}
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("SMTP_", "EMAIL_"))})
    return env


def send_email(subject, body, env):
    host = env.get("SMTP_HOST", "smtp.gmail.com")
    port = int(env.get("SMTP_PORT", "465"))
    user = env.get("SMTP_USER")
    password = env.get("SMTP_PASSWORD")
    to_addr = env.get("EMAIL_TO", DEFAULT_EMAIL_TO)
    from_addr = env.get("EMAIL_FROM", user)

    if not user or not password:
        print("⚠️  No SMTP_USER/SMTP_PASSWORD found (.env or env vars). Email NOT sent.")
        print("    Report was still saved locally.")
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                s.login(user, password)
                s.sendmail(from_addr, [to_addr], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls()
                s.login(user, password)
                s.sendmail(from_addr, [to_addr], msg.as_string())
        print(f"✅ Email sent to {to_addr}")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False


# --- Main -----------------------------------------------------------------
MAX_DRIVER_RESTARTS = 3  # consecutive dead-session restarts before giving up


def _restart_driver(driver):
    """Replace a dead browser session with a fresh, warmed-up one."""
    try:
        driver.quit()
    except Exception:
        pass
    driver = build_driver()
    driver.get("https://www.flyfrontier.com/")
    time.sleep(5)
    return driver


def _fetch_route(driver, url):
    driver.get(url)
    time.sleep(PAGE_WAIT)
    return parse_flights(driver.page_source)


def search_group(driver, destinations, target_dt, is_intl):
    """Search every origin -> dest in `destinations` for target_dt.

    Returns (deals, routes_checked, driver). The driver is returned because a
    mid-run Chrome crash (InvalidSessionIdException etc.) triggers a rebuild;
    the caller must keep using the returned instance.
    """
    iso = target_dt.strftime("%Y-%m-%d")
    display = target_dt.strftime("%b %-d, %Y")
    date_url = display.replace(" ", "%20")
    label = "INT'L" if is_intl else "CONUS"

    if is_blackout_date(iso):
        print(f"🚫 {label} date {display} ({iso}) is a blackout date - skipping group.")
        return [], 0, driver

    deals = []
    routes = 0
    consecutive_restarts = 0
    for origin in ORIGINS:
        for dest_code, dest_name in destinations.items():
            routes += 1
            url = (
                f"https://booking.flyfrontier.com/Flight/InternalSelect?"
                f"o1={origin}&d1={dest_code}&dd1={date_url}&ADT=1&mon=true&promo="
            )
            print(f"  {label} {origin}->{dest_code} ({display})...", end=" ", flush=True)
            try:
                try:
                    flights = _fetch_route(driver, url)
                except Exception as e:
                    # A dead session surfaces as InvalidSessionIdException,
                    # MaxRetryError, etc. depending on how Chrome died — treat
                    # any fetch failure as session-suspect: restart Chrome and
                    # retry the route once, otherwise every remaining route
                    # errors out too.
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
                    flights = _fetch_route(driver, url)
                found = extract_deals(
                    flights, origin, dest_code, dest_name, display, is_intl
                )
                deals.extend(found)
                gw = sum(1 for d in found if d["type"] == "GoWild")
                dd = sum(1 for d in found if d["type"] == "Discount Den")
                print(f"{len(flights)} flights (GW:{gw} DD:{dd})")
                consecutive_restarts = 0
            except Exception as e:
                print(f"error: {type(e).__name__}")
            time.sleep(BETWEEN_REQUESTS)
    return deals, routes, driver


def main():
    now = datetime.now()
    conus_dt = now + timedelta(days=1)    # domestic: next day
    intl_dt = now + timedelta(days=10)    # international: 10 days out

    conus_display = conus_dt.strftime("%b %-d, %Y")
    intl_display = intl_dt.strftime("%b %-d, %Y")

    print("=" * 60)
    print("FRONTIER DEAL CHECKER")
    print(f"  CONUS (next day):   {conus_display}")
    print(f"  Int'l (10 days out): {intl_display}")
    print(f"  Origins: {', '.join(ORIGINS)}  |  headless={HEADLESS}")
    print("=" * 60)

    driver = build_driver()
    all_deals = []
    routes_checked = 0
    try:
        # Warm up
        driver.get("https://www.flyfrontier.com/")
        time.sleep(5)

        d1, r1, driver = search_group(
            driver, DOMESTIC_DESTINATIONS, conus_dt, is_intl=False
        )
        d2, r2, driver = search_group(
            driver, INTERNATIONAL_DESTINATIONS, intl_dt, is_intl=True
        )
        all_deals = d1 + d2
        routes_checked = r1 + r2
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # Blackout note
    notes = []
    if is_blackout_date(conus_dt.strftime("%Y-%m-%d")):
        notes.append(f"{conus_display} (CONUS)")
    if is_blackout_date(intl_dt.strftime("%Y-%m-%d")):
        notes.append(f"{intl_display} (Int'l)")
    blackout_note = ", ".join(notes) if notes else "None"

    meta = {
        "conus_date": conus_display,
        "intl_date": intl_display,
        "routes_checked": routes_checked,
        "blackout_note": blackout_note,
        "generated": now.strftime("%Y-%m-%d %H:%M:%S PT"),
    }

    # Cruise deals (VacationsToGo). Weekly-cached: only scrapes on a cache miss,
    # and when it does it opens a brief headful window (headless is blocked there).
    print("\n" + "=" * 60)
    print("CRUISE DEALS (VacationsToGo, weekly)")
    print("=" * 60)
    n_cruise = 0
    try:
        from cruise_deals import build_cruise_section, get_cruise_deals

        c_deals, c_when, c_cached = get_cruise_deals()
        n_cruise = len(c_deals)
        cruise_section = build_cruise_section(c_deals, c_when, c_cached)
    except Exception as e:
        print(f"  cruise check failed: {type(e).__name__}: {e}")
        cruise_section = (
            "TOP 10 CRUISE DEALS — VacationsToGo\n"
            + "-" * 40
            + f"\n   (cruise check failed: {type(e).__name__})\n"
        )

    report = build_report(all_deals, meta, cruise_section=cruise_section)
    print("\n" + report)

    # Save a copy
    results_dir = os.path.join(BASE_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(
        results_dir, f"deal_report_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    )
    with open(out_path, "w") as f:
        f.write(report)
    print(f"\n💾 Saved report to {out_path}")

    # Email
    env = load_env()
    subject = (
        f"Frontier + Cruise Deals — {len(all_deals)} flights, "
        f"{n_cruise} cruises ({conus_display} / {intl_display})"
    )
    send_email(subject, report, env)


if __name__ == "__main__":
    main()
