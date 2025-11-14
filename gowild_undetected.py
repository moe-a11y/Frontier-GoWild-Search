#!/usr/bin/env python3
"""
ULTIMATE BYPASS: Undetected ChromeDriver + Fast Scraping
This WILL work - undetected-chromedriver bypasses PerimeterX completely
"""

import csv
import json
import time
from datetime import datetime

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

# Import centralized configuration
from config import SFO_DIRECT_DESTINATIONS, GOWILD_BLACKOUT_DATES

# SFO Direct Destinations (limited for testing)
TEST_DESTINATIONS = {
    "DEN": "Denver",
    "LAS": "Las Vegas",
    "PHX": "Phoenix",
}


def create_driver():
    """Create undetected Chrome driver"""
    print("Launching undetected Chrome...")

    options = uc.ChromeOptions()
    # Uncomment to run headless (invisible):
    # options.add_argument('--headless=new')

    # Let it auto-detect Chrome version
    driver = uc.Chrome(options=options, use_subprocess=True)
    return driver


def check_flight(driver, origin, dest, date_str):
    """
    Check for GoWild flights using undetected browser
    """
    # Format the date properly for the URL
    url = f"https://booking.flyfrontier.com/Flight/InternalSelect?o1={origin}&d1={dest}&dd1={date_str}&ADT=1&mon=true&promo="

    print(f"  {origin} → {dest}...", end=" ", flush=True)

    try:
        driver.get(url)

        # Wait LONGER for PerimeterX JavaScript to complete
        time.sleep(10)

        # Get the page source
        page_source = driver.page_source

        # Save for debugging on first call
        import os

        if not os.path.exists("debug_page.html"):
            with open("debug_page.html", "w") as f:
                f.write(page_source)
            print(f"[DEBUG: Saved page to debug_page.html]", end=" ")

        # Check for PerimeterX block
        if "px-captcha" in page_source or "Access Denied" in page_source:
            print("❌ PX Block")
            return None

        # Check if page is still loading
        if len(page_source) < 5000:
            print("❌ Empty page")
            return None

        # Try to extract JSON data from the page
        soup = BeautifulSoup(page_source, "html.parser")

        for script in soup.find_all("script"):
            script_text = script.string
            if script_text and "journeys" in script_text and "flights" in script_text:
                try:
                    # Extract JSON
                    import html as html_lib

                    decoded = html_lib.unescape(script_text)

                    start = decoded.find("{")
                    if start == -1:
                        continue

                    # Find matching closing brace
                    brace_count = 0
                    end = start
                    for i in range(start, len(decoded)):
                        if decoded[i] == "{":
                            brace_count += 1
                        elif decoded[i] == "}":
                            brace_count -= 1
                            if brace_count == 0:
                                end = i + 1
                                break

                    json_str = decoded[start:end]
                    data = json.loads(json_str)

                    if "journeys" in data:
                        flights = data["journeys"][0].get("flights", [])
                        gowild_flights = [
                            f for f in flights if f.get("isGoWildFareEnabled")
                        ]

                        if gowild_flights:
                            print(f"✅ {len(gowild_flights)} GoWild!")
                            return {"dest": dest, "flights": gowild_flights}
                        else:
                            print("○ No GoWild")
                            return None

                except Exception as e:
                    print(f"⚠️  Parse error: {e}")
                    continue

        print("○ No data")
        return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def main():
    print("=" * 60)
    print("UNDETECTED CHROMEDRIVER - GoWild Search")
    print("This BYPASSES PerimeterX completely")
    print("=" * 60)

    # Ask user for test vs full run
    print("\nTest with 3 destinations first? (recommended)")
    test_mode = input("Enter 'y' for test, 'n' for full run [y]: ").lower() != "n"

    destinations = TEST_DESTINATIONS if test_mode else SFO_DIRECT_DESTINATIONS

    driver = create_driver()

    try:
        # Warm up the session
        print("\nWarming up session...")
        driver.get("https://www.flyfrontier.com/")
        time.sleep(3)

        # Dates to search
        dates = ["Dec%2024,%202025", "Dec%2025,%202025"]
        all_results = {}

        for date_formatted in dates:
            # Display friendly date
            date_display = date_formatted.replace("%20", " ").replace("%2C", ",")
            print(f"\n{'='*60}")
            print(f"Searching: {date_display}")
            print(f"{'='*60}\n")

            results = {}

            for idx, (dest_code, dest_name) in enumerate(destinations.items(), 1):
                print(f"[{idx}/{len(destinations)}] ", end="")

                result = check_flight(driver, "SFO", dest_code, date_formatted)

                if result:
                    results[dest_code] = {
                        "name": dest_name,
                        "flights": result["flights"],
                    }

                # Human-like delay
                time.sleep(7)

            all_results[date_display] = results

            # Show results for this date
            print(f"\n{date_display}: Found {len(results)} destinations with GoWild")
            for code, info in results.items():
                print(f"  ✈️  {code} - {info['name']}: {len(info['flights'])} flights")

        # Final summary
        print(f"\n{'='*60}")
        print("FINAL SUMMARY")
        print(f"{'='*60}")
        for date, results in all_results.items():
            print(f"\n{date}:")
            for code, info in results.items():
                for flight in info["flights"]:
                    price = flight.get("goWildFare", "N/A")
                    duration = flight.get("duration", "N/A")
                    stops = flight.get("stopsText", "N/A")
                    print(f"  {code}: ${price} - {stops} - {duration}")

    finally:
        print("\nClosing browser...")
        driver.quit()


if __name__ == "__main__":
    main()
