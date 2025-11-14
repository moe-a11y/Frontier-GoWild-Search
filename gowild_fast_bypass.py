#!/usr/bin/env python3
"""
Optimized GoWild scraper using curl_cffi to bypass PerimeterX
curl_cffi uses libcurl with Chrome's TLS fingerprint - bypasses TLS-based bot detection
"""

import csv
import html, json, random, time
from datetime import datetime, timedelta

try:
    from curl_cffi import requests

    print("✅ Using curl_cffi (Chrome TLS fingerprint)")
except ImportError:
    print("❌ curl_cffi not installed. Installing...")
    print("Run: pip3 install curl-cffi")
    import sys

    sys.exit(1)

from bs4 import BeautifulSoup

# Import centralized configuration
from config import SFO_DIRECT_DESTINATIONS, GOWILD_BLACKOUT_DATES


def create_session():
    """Create a session that mimics Chrome browser exactly with session warming"""
    # Use curl_cffi's Session which impersonates Chrome
    session = requests.Session()

    print("Establishing and warming up session with Frontier...")
    try:
        # Step 1: Visit homepage to get initial cookies
        print("  1. Visiting homepage...")
        response = session.get(
            "https://www.flyfrontier.com/", impersonate="chrome120", timeout=15
        )
        print(f"     Status: {response.status_code}")
        time.sleep(random.uniform(3, 5))

        # Step 2: Visit another page to establish browsing pattern
        print("  2. Visiting travel page...")
        response = session.get(
            "https://www.flyfrontier.com/travel/", impersonate="chrome120", timeout=15
        )
        print(f"     Status: {response.status_code}")
        time.sleep(random.uniform(2, 4))

        # Step 3: Visit deals page (closer to what we're actually doing)
        print("  3. Visiting deals page...")
        response = session.get(
            "https://www.flyfrontier.com/deals/", impersonate="chrome120", timeout=15
        )
        print(f"     Status: {response.status_code}")
        time.sleep(random.uniform(2, 4))

        print(f"✅ Session warmed up successfully")
        print(f"   Cookies: {len(session.cookies)} cookies set")
        return session
    except Exception as e:
        print(f"⚠️  Warning during session setup: {e}")
        return session


def get_flight_data(origin, dest, date, session):
    """Get flight data for a single route using Chrome impersonation"""
    url = f"https://booking.flyfrontier.com/Flight/InternalSelect?o1={origin}&d1={dest}&dd1={date}&ADT=1&mon=true&promo="

    try:
        response = session.get(
            url,
            impersonate="chrome120",  # Mimic Chrome 120's TLS fingerprint
            timeout=15,
        )

        if response.status_code == 403:
            print("⚠️  403 - Still blocked, trying different impersonation...")
            # Try different browser impersonation
            response = session.get(url, impersonate="chrome116", timeout=15)
            if response.status_code == 403:
                return None, True

        if response.status_code != 200:
            return None, False

        # Check for CAPTCHA in content
        if "px-captcha" in response.text or len(response.text) < 10000:
            return None, True

        # Extract flight data (same logic as original)
        soup = BeautifulSoup(response.text, "html.parser")

        for script in soup.find_all("script"):
            script_text = script.string
            if script_text and "journeys" in script_text and "flights" in script_text:
                try:
                    decoded_data = html.unescape(script_text)
                    start = decoded_data.find("{")
                    if start == -1:
                        continue

                    brace_count = 0
                    end = start
                    for i in range(start, len(decoded_data)):
                        if decoded_data[i] == "{":
                            brace_count += 1
                        elif decoded_data[i] == "}":
                            brace_count -= 1
                            if brace_count == 0:
                                end = i + 1
                                break

                    json_str = decoded_data[start:end]
                    data = json.loads(json_str)

                    if "journeys" in data:
                        return data, False
                except json.JSONDecodeError:
                    continue
                except Exception:
                    continue

        return None, False

    except Exception as e:
        print(f"    Error: {e}")
        return None, False


def scan_routes(origin, destinations, date):
    """Scan all routes from an origin"""
    session = create_session()
    results = {}

    print(f"\n🔍 Scanning {len(destinations)} routes from {origin}...\n")

    base_delay = 12  # More conservative delay

    for idx, (dest_code, dest_name) in enumerate(destinations.items(), 1):
        delay = random.uniform(base_delay, base_delay + 8)

        print(
            f"[{idx}/{len(destinations)}] {origin} → {dest_code} ({dest_name})", end=" "
        )
        print(f"(waiting {delay:.1f}s)...", end=" ", flush=True)

        time.sleep(delay)

        data, hit_limit = get_flight_data(origin, dest_code, date, session)

        if hit_limit:
            print("❌ Rate limited - increasing delay")
            base_delay = min(base_delay + 10, 60)
            continue

        if data and "journeys" in data:
            try:
                flights = data["journeys"][0].get("flights")
                if flights:
                    gowild = [f for f in flights if f.get("isGoWildFareEnabled")]

                    if gowild:
                        results[dest_code] = {
                            "name": dest_name,
                            "count": len(gowild),
                            "flights": gowild,
                        }
                        print(f"✅ {len(gowild)} GoWild flights!")
                    else:
                        print("○ No GoWild flights")
                else:
                    print("○ No flights")
            except (KeyError, IndexError, TypeError):
                print("○ No flights")
        else:
            print("○ No data")

        if not hit_limit and base_delay > 12:
            base_delay = max(base_delay - 2, 12)

    return results


def export_to_csv(origin, results, date_str):
    """Export results to CSV file"""
    if not results:
        print("No results to export")
        return

    filename = f"gowild_results_{origin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with open(filename, "w", newline="") as csvfile:
        fieldnames = [
            "Origin",
            "Destination_Code",
            "Destination_Name",
            "Flight_Date",
            "Price",
            "Duration",
            "Stops",
            "Seats_Remaining",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for dest_code, info in results.items():
            for flight in info["flights"]:
                writer.writerow(
                    {
                        "Origin": origin,
                        "Destination_Code": dest_code,
                        "Destination_Name": info["name"],
                        "Flight_Date": date_str.replace("%20", " "),
                        "Price": flight.get("goWildFare", "N/A"),
                        "Duration": flight.get("duration", "N/A"),
                        "Stops": flight.get("stopsText", "N/A"),
                        "Seats_Remaining": flight.get(
                            "goWildFareSeatsRemaining", "N/A"
                        ),
                    }
                )

    print(f"\n✅ Results exported to: {filename}")
    return filename


def display_results(origin, results):
    """Display the results"""
    print(f"\n{'='*60}")
    print(f"RESULTS: GoWild Flights from {origin}")
    print(f"{'='*60}\n")

    if not results:
        print("No GoWild flights found 😔")
        return

    for dest_code, info in results.items():
        print(f"✈️  {origin} → {dest_code} ({info['name']})")
        print(f"   {info['count']} GoWild flight(s) available")

        for flight in info["flights"][:3]:
            print(
                f"   • ${flight.get('goWildFare')} - {flight.get('stopsText')} - {flight.get('duration')}"
            )

        print()


if __name__ == "__main__":
    print("=" * 60)
    print("Frontier GoWild Search - PerimeterX Bypass Edition")
    print("Using curl_cffi with Chrome TLS fingerprint")
    print("=" * 60)

    origin = "SFO"
    dates_to_search = [
        datetime(2025, 12, 24),
        datetime(2025, 12, 25),
    ]

    all_results = {}

    for date_obj in dates_to_search:
        date_str_check = date_obj.strftime("%Y-%m-%d")
        if date_str_check in GOWILD_BLACKOUT_DATES_2025:
            print(f"\n🚫 BLACKOUT DATE: {date_obj.strftime('%A, %B %d, %Y')}")
            continue

        date_str = date_obj.strftime("%b-%d,-%Y").replace("-", "%20")
        print(f"\n{'='*60}")
        print(f"Searching: {date_obj.strftime('%A, %B %d, %Y')}")
        print(f"{'='*60}")

        results = scan_routes(origin, SFO_DIRECT_DESTINATIONS, date_str)
        display_results(origin, results)

        if results:
            export_to_csv(origin, results, date_str)

        all_results[date_str_check] = results

    # Summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    for date_key, results in all_results.items():
        print(f"{date_key}: {len(results)} destinations with GoWild")
