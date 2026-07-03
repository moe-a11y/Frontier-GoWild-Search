#!/usr/bin/env python3
"""
WORKING SOLUTION: Manual CAPTCHA solving + Automation
You solve ONE CAPTCHA, then the script automates the rest
"""

import csv
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

# Import centralized configuration
from config import ORIGINS, SFO_DIRECT_DESTINATIONS, is_blackout_date


def build_driver():
    """Create an undetected Chrome driver that works on Apple Silicon.

    On arm64 macOS, undetected-chromedriver downloads an x86_64 driver and/or
    patches the binary in a way that breaks its code signature (macOS then kills
    it with SIGKILL). To avoid both problems we:
      1. Let Selenium Manager resolve the correct arch-matched chromedriver.
      2. Copy it and apply an ad-hoc code signature so Gatekeeper allows it.
      3. Disable uc's own patch/download step (modern chromedrivers no longer
         contain the cdc_ artifact uc looks for, so patching only risks
         re-breaking the signature).
    """
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
    return uc.Chrome(
        use_subprocess=True, driver_executable_path=signed, version_main=version_main
    )


def main():
    # Search for flights leaving TOMORROW (GoWild booking window)
    travel_day = datetime.today() + timedelta(days=1)
    travel_iso = travel_day.strftime("%Y-%m-%d")
    date_display = travel_day.strftime("%b %-d, %Y")  # e.g. "Jul 3, 2026"
    date_url = date_display.replace(" ", "%20")  # e.g. "Jul%203,%202026"

    print("=" * 70)
    print(f"FRONTIER GOWILD SEARCH - OUTBOUND FROM {', '.join(ORIGINS)}")
    print("=" * 70)

    # Respect GoWild blackout dates - no GoWild fares are sold on these days
    if is_blackout_date(travel_iso):
        print(f"\n🚫 {date_display} ({travel_iso}) is a GoWild BLACKOUT DATE.")
        print("   No GoWild fares are available for travel on this day.")
        print("   Nothing to search - exiting.")
        return

    num_dests = len(SFO_DIRECT_DESTINATIONS)
    print("\n📋 INSTRUCTIONS:")
    print("1. The browser will open")
    print("2. SOLVE THE CAPTCHA when it appears (Press & Hold)")
    print(
        f"3. Script will search FROM {', '.join(ORIGINS)} to {num_dests} destinations on {date_display}"
    )
    print("4. Sit back and let it run (~1 min per destination per origin)")
    print("\n" + "=" * 70)

    input("\nPress Enter to start...")

    # Create driver
    print("\nLaunching browser...")
    driver = build_driver()

    try:
        # Visit the first search to trigger CAPTCHA
        print("\n🔐 Loading first search - YOU MUST SOLVE THE CAPTCHA!")
        print(f"   Route: SFO → DEN on {date_display}")

        driver.get(
            f"https://booking.flyfrontier.com/Flight/InternalSelect?o1=SFO&d1=DEN&dd1={date_url}&ADT=1&mon=true&promo="
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

        # Now search all routes - OUTBOUND FROM EACH ORIGIN (SFO, SJC)
        all_results = {}
        results = {}  # keyed by "ORIGIN-DEST"

        for origin in ORIGINS:
            print(f"\n{'='*70}")
            print(f"Searching OUTBOUND flights FROM {origin}: {date_display}")
            print(f"{'='*70}\n")

            for idx, (dest_code, dest_name) in enumerate(
                SFO_DIRECT_DESTINATIONS.items(), 1
            ):
                print(
                    f"[{idx}/{len(SFO_DIRECT_DESTINATIONS)}] {origin} → {dest_code} ({dest_name})...",
                    end=" ",
                    flush=True,
                )

                url = f"https://booking.flyfrontier.com/Flight/InternalSelect?o1={origin}&d1={dest_code}&dd1={date_url}&ADT=1&mon=true&promo="
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
                                    results[f"{origin}-{dest_code}"] = {
                                        "origin": origin,
                                        "dest": dest_code,
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
        print(f"\nFound {len(results)} routes with GoWild on {date_display}")

        # Export results
        print(f"\n{'='*70}")
        print("FINAL RESULTS")
        print("=" * 70)

        csv_data = []
        for date, results in all_results.items():
            print(f"\n{date}:")
            for _key, info in results.items():
                for flight in info["flights"]:
                    price = flight.get("goWildFare", "N/A")
                    duration = flight.get("duration", "N/A")
                    stops = flight.get("stopsText", "N/A")
                    seats = flight.get("goWildFareSeatsRemaining", "N/A")

                    print(
                        f"  {info['origin']} → {info['dest']} ({info['name']}): ${price} - {stops} - {duration} - {seats} seats"
                    )

                    csv_data.append(
                        {
                            "Date": date,
                            "Origin": info["origin"],
                            "Destination": f"{info['dest']} ({info['name']})",
                            "Price": price,
                            "Duration": duration,
                            "Stops": stops,
                            "Seats": seats,
                        }
                    )

        # Save CSV
        filename = f"gowild_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "Date",
                    "Origin",
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
