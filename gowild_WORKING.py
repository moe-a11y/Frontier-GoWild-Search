#!/usr/bin/env python3
"""
WORKING SOLUTION: Manual CAPTCHA solving + Automation
You solve ONE CAPTCHA, then the script automates the rest
"""

import csv
import json
import time
from datetime import datetime

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

SFO_DIRECT_DESTINATIONS = {
    "DEN": "Denver",
    "LAS": "Las Vegas",
    "PHX": "Phoenix",
    "ATL": "Atlanta",
    "ORD": "Chicago O'Hare",
    "DFW": "Dallas/Fort Worth",
    "ONT": "Ontario, CA",
    "SAN": "San Diego",
    "SNA": "Orange County",
    "AUS": "Austin",
    "IAH": "Houston",
    "SAT": "San Antonio",
    "MCO": "Orlando",
    "MIA": "Miami",
    "FLL": "Fort Lauderdale",
    "TPA": "Tampa",
    "SEA": "Seattle",
    "PDX": "Portland, OR",
    "SLC": "Salt Lake City",
    "MSP": "Minneapolis",
    "DTW": "Detroit",
    "BNA": "Nashville",
    "CLT": "Charlotte",
    "PHL": "Philadelphia",
    "BWI": "Baltimore",
}


def main():
    print("=" * 70)
    print("FRONTIER GOWILD SEARCH - OUTBOUND FROM SFO")
    print("=" * 70)
    print("\n📋 INSTRUCTIONS:")
    print("1. The browser will open")
    print("2. SOLVE THE CAPTCHA when it appears (Press & Hold)")
    print("3. Script will search FROM SFO to 25 destinations on Jan 2")
    print("4. Sit back and let it run (~25 minutes for all destinations)")
    print("\n" + "=" * 70)

    input("\nPress Enter to start...")

    # Create driver
    print("\nLaunching browser...")
    driver = uc.Chrome(use_subprocess=True)

    try:
        # Visit the first search to trigger CAPTCHA
        print("\n🔐 Loading first search - YOU MUST SOLVE THE CAPTCHA!")
        print("   Route: SFO → DEN on Jan 2, 2026")

        driver.get(
            "https://booking.flyfrontier.com/Flight/InternalSelect?o1=SFO&d1=DEN&dd1=Jan%202,%202026&ADT=1&mon=true&promo="
        )

        print("\n⏳ Waiting for page to load...")
        print("   👉 If you see a CAPTCHA, solve it (Press & Hold)")
        print("   👉 If page loads normally, just wait...")

        time.sleep(8)  # Wait for page to fully load

        # Check if CAPTCHA appeared
        if "px-captcha" in driver.page_source:
            print("\n⚠️  CAPTCHA detected - please solve it now")
            input("Press Enter AFTER solving the CAPTCHA...")
        else:
            print("\n✅ Page loaded successfully - NO CAPTCHA needed!")

        print("\n🎉 CAPTCHA SOLVED! Now automating the rest...")

        # Now search all routes - OUTBOUND FROM SFO
        all_results = {}
        dates = [
            ("Jan 2, 2026", "Jan%202,%202026"),
        ]

        for date_display, date_url in dates:
            print(f"\n{'='*70}")
            print(f"Searching OUTBOUND flights FROM SFO: {date_display}")
            print(f"{'='*70}\n")

            results = {}

            for idx, (dest_code, dest_name) in enumerate(
                SFO_DIRECT_DESTINATIONS.items(), 1
            ):
                print(
                    f"[{idx}/{len(SFO_DIRECT_DESTINATIONS)}] SFO → {dest_code} ({dest_name})...",
                    end=" ",
                    flush=True,
                )

                url = f"https://booking.flyfrontier.com/Flight/InternalSelect?o1=SFO&d1={dest_code}&dd1={date_url}&ADT=1&mon=true&promo="
                driver.get(url)
                time.sleep(8)  # Wait for page load

                page_source = driver.page_source

                # Check for block (shouldn't happen after initial CAPTCHA)
                if "px-captcha" in page_source:
                    print("⚠️  CAPTCHA again - please solve")
                    input("Press Enter after solving...")
                    page_source = driver.page_source

                # Parse flight data
                try:
                    soup = BeautifulSoup(page_source, "html.parser")

                    for script in soup.find_all("script"):
                        script_text = script.string
                        if (
                            script_text
                            and "journeys" in script_text
                            and "flights" in script_text
                        ):
                            import html as html_lib

                            decoded = html_lib.unescape(script_text)

                            start = decoded.find("{")
                            if start == -1:
                                continue

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

                            data = json.loads(decoded[start:end])

                            if "journeys" in data:
                                flights = data["journeys"][0].get("flights", [])
                                gowild = [
                                    f for f in flights if f.get("isGoWildFareEnabled")
                                ]

                                if gowild:
                                    results[dest_code] = {
                                        "name": dest_name,
                                        "flights": gowild,
                                    }
                                    print(f"✅ {len(gowild)} GoWild!")
                                    break
                                else:
                                    print("○ No GoWild")
                                    break
                    else:
                        print("○ No data")

                except Exception as e:
                    print(f"❌ Error: {e}")

            all_results[date_display] = results
            print(f"\nFound {len(results)} destinations with GoWild on {date_display}")

        # Export results
        print(f"\n{'='*70}")
        print("FINAL RESULTS")
        print("=" * 70)

        csv_data = []
        for date, results in all_results.items():
            print(f"\n{date}:")
            for code, info in results.items():
                for flight in info["flights"]:
                    price = flight.get("goWildFare", "N/A")
                    duration = flight.get("duration", "N/A")
                    stops = flight.get("stopsText", "N/A")
                    seats = flight.get("goWildFareSeatsRemaining", "N/A")

                    print(
                        f"  {code} ({info['name']}): ${price} - {stops} - {duration} - {seats} seats"
                    )

                    csv_data.append(
                        {
                            "Date": date,
                            "Destination": f"{code} ({info['name']})",
                            "Price": price,
                            "Duration": duration,
                            "Stops": stops,
                            "Seats": seats,
                        }
                    )

        # Save CSV
        filename = f"gowild_results_SFO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "Date",
                    "Destination",
                    "Price",
                    "Duration",
                    "Stops",
                    "Seats",
                ],
            )
            writer.writeheader()
            writer.writerows(csv_data)

        print(f"\n✅ Results saved to: {filename}")

    finally:
        print("\nKeeping browser open for your review...")
        input("Press Enter to close browser...")
        driver.quit()


if __name__ == "__main__":
    main()
