#!/usr/bin/env python3
"""
VacationsToGo cruise deal checker.

Opens the VacationsToGo "ticker" (last-minute deals), signs in with the member
email (VacationsToGo lets returning members in with just an email; if the account
does not exist yet it registers once), and finds the best cruise deals matching:
  - highest "You Save" percentage (ranked)
  - 10 nights or less
  - departing OR ending in San Francisco, Los Angeles, or anywhere in Florida
  - sale price < $1000 USD

Results are cached to results/cruise_deals.json. VacationsToGo deals do not change
often, so a fresh scrape only runs if the cache is older than CACHE_MAX_AGE_DAYS
(default 7). Otherwise the last-checked deals are returned.

Run standalone:  python3 cruise_deals.py [--force]
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

# Reuse the arch-safe Chrome driver builder from the flight checker.
from gowild_deal_report import build_driver

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, "results", "cruise_deals.json")
CACHE_MAX_AGE_DAYS = 7

TICKER_URL = "https://www.vacationstogo.com/ticker.cfm?t=y&sp=y"
HOME_URL = "https://www.vacationstogo.com/"
# Email used to sign in / register on VacationsToGo.
VTG_EMAIL = os.environ.get("VTG_EMAIL", "muhammadalinajfi1@gmail.com")

# Filters
MAX_NIGHTS = 10
MAX_PRICE = 1000
TOP_N = 10
# from OR to port must contain one of these; label -> substrings
PORT_TARGETS = {
    "SF": ["San Francisco"],
    "LA": ["Los Angeles"],
    "FL": [", FL", ", Florida"],
}


# --- Parsing --------------------------------------------------------------
def _money(s):
    m = re.search(r"\$([\d,]+)", s or "")
    return int(m.group(1).replace(",", "")) if m else None


def _pct(s):
    m = re.search(r"(\d+)\s*%", s or "")
    return int(m.group(1)) if m else None


def _port_tags(frm, to):
    tags = []
    for label, needles in PORT_TARGETS.items():
        if any(n in frm for n in needles) or any(n in to for n in needles):
            tags.append(label)
    return tags


def parse_ticker(html):
    """Parse every deal row from the ticker page, deduped by deal id.

    Row columns: #id | nights | sail date | from port | to port | line/ship |
                 rating | was $ | now $ | save % | note
    """
    soup = BeautifulSoup(html, "html.parser")
    deals = {}
    for tbl in soup.find_all("table"):
        for tr in tbl.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
            if len(cells) < 11 or not re.match(r"#\d+", cells[0]):
                continue
            line, ship = cells[5], ""
            if " / " in cells[5]:
                line, ship = cells[5].split(" / ", 1)
            deals[cells[0]] = {
                "id": cells[0],
                "nights": int(cells[1]) if cells[1].isdigit() else None,
                "sail": cells[2],
                "from": cells[3],
                "to": cells[4],
                "line": line.strip(),
                "ship": ship.strip(),
                "was": _money(cells[7]),
                "now": _money(cells[8]),
                "save": _pct(cells[9]),
                "note": cells[10],
            }
    return list(deals.values())


def filter_and_rank(deals, top_n=TOP_N):
    matched = []
    for d in deals:
        if d["nights"] is None or d["nights"] > MAX_NIGHTS:
            continue
        if d["now"] is None or d["now"] >= MAX_PRICE:
            continue
        if d["save"] is None:
            continue
        tags = _port_tags(d["from"], d["to"])
        if not tags:
            continue
        d["tags"] = tags
        matched.append(d)
    matched.sort(key=lambda x: x["save"], reverse=True)
    return matched[:top_n]


# --- Browser flow ---------------------------------------------------------
def _safe_get(driver, url, tries=3):
    for i in range(tries):
        try:
            driver.get(url)
            return True
        except Exception as e:
            print(f"  get attempt {i + 1} failed: {type(e).__name__}")
            time.sleep(5)
    return False


def login_and_load_ticker(driver):
    """Warm up, load the ticker, sign in with email (register if needed), return HTML."""
    _safe_get(driver, HOME_URL)
    time.sleep(5)
    _safe_get(driver, TICKER_URL)
    time.sleep(6)

    # If we were redirected to the login page, sign in with the member email.
    if "login" in driver.current_url.lower():
        print("  signing in with member email...")
        try:
            el = driver.find_element(By.NAME, "LogEmail")
            el.clear()
            el.send_keys(VTG_EMAIL)
            el.send_keys(Keys.RETURN)
            time.sleep(8)
        except Exception as e:
            print(f"  email login field not found: {type(e).__name__}")

    # If still not on the ticker, try one-time registration.
    if not parse_ticker(driver.page_source):
        if "login" in driver.current_url.lower():
            print("  registering new member account...")
            try:
                driver.find_element(By.NAME, "FirstName").send_keys("Muhammad")
                driver.find_element(By.NAME, "LastName").send_keys("Ali")
                driver.find_element(By.NAME, "Email").send_keys(VTG_EMAIL)
                driver.find_element(By.NAME, "VerifyEmail").send_keys(VTG_EMAIL)
                driver.find_element(By.NAME, "Zip").send_keys("94103")
                try:
                    Select(driver.find_element(By.NAME, "Country")).select_by_visible_text(
                        "United States"
                    )
                except Exception:
                    pass
                driver.find_element(By.ID, "newUser_SubmitDefault").click()
                time.sleep(9)
            except Exception as e:
                print(f"  registration failed: {type(e).__name__}")

        # Reload the ticker now that we should be authenticated.
        _safe_get(driver, TICKER_URL)
        time.sleep(8)

    return driver.page_source


def scrape_cruise_deals(headless=None):
    # VacationsToGo resets connections to headless Chrome, so run headful.
    # (This only happens on a cache miss — about once a week.)
    if headless is None:
        headless = False
    driver = build_driver(headless=headless)
    try:
        html = login_and_load_ticker(driver)
        all_deals = parse_ticker(html)
        print(f"  parsed {len(all_deals)} cruise deals from ticker")
        top = filter_and_rank(all_deals)
        print(f"  {len(top)} match filters (<= {MAX_NIGHTS}n, < ${MAX_PRICE}, SF/LA/FL)")
        return top
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# --- Cache ----------------------------------------------------------------
def _load_cache():
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(deals, checked_at):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"checked_at": checked_at, "deals": deals}, f, indent=2)


def get_cruise_deals(force=False, headless=None):
    """Return (deals, checked_at_iso, from_cache).

    Only scrapes if the cache is missing/stale (older than CACHE_MAX_AGE_DAYS) or
    force=True; otherwise returns the last checked deals.
    """
    cache = _load_cache()
    if not force and cache and cache.get("checked_at"):
        try:
            age = datetime.now() - datetime.fromisoformat(cache["checked_at"])
            if age < timedelta(days=CACHE_MAX_AGE_DAYS):
                print(
                    f"  using cached cruise deals from {cache['checked_at']} "
                    f"(age {age.days}d < {CACHE_MAX_AGE_DAYS}d)"
                )
                return cache["deals"], cache["checked_at"], True
        except ValueError:
            pass

    print("  cache stale or missing - scraping VacationsToGo...")
    checked_at = datetime.now().isoformat(timespec="seconds")
    deals = scrape_cruise_deals(headless=headless)
    _save_cache(deals, checked_at)
    return deals, checked_at, False


# --- Report section -------------------------------------------------------
def build_cruise_section(deals, checked_at, from_cache):
    lines = []
    lines.append("TOP 10 CRUISE DEALS — VacationsToGo (<=10 nights, <$1000, SF/LA/FL)")
    lines.append("-" * 40)
    if deals:
        for i, d in enumerate(deals, 1):
            ship = d.get("ship") or d.get("line") or "Cruise"
            line = d.get("line", "")
            was = f"${d['was']:,}" if d.get("was") else "N/A"
            head = f"{i:>4}. {ship} ({line}) — ${d['now']:,}"
            head += f"  ·  {d['save']}% off (was {was})"
            itin = (
                f"      {d['from']} > {d['to']} | {d['nights']} nights | "
                f"Departs {d['sail']}"
            )
            lines.append(head)
            lines.append(itin + "\n")
    else:
        lines.append("   (none found)\n")
    when = checked_at.split("T")[0] if checked_at else "unknown"
    cache_note = " (cached)" if from_cache else ""
    lines.append(f"Cruise data checked: {when}{cache_note}  ·  refreshed weekly")
    return "\n".join(lines)


# --- Standalone -----------------------------------------------------------
def main():
    force = "--force" in sys.argv
    print("=" * 60)
    print("VACATIONSTOGO CRUISE DEAL CHECKER")
    print("=" * 60)
    deals, checked_at, from_cache = get_cruise_deals(force=force)
    section = build_cruise_section(deals, checked_at, from_cache)
    print("\n" + section)


if __name__ == "__main__":
    main()
