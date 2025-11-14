#!/usr/bin/env python3
"""
Round-trip GoWild flight finder
Searches outbound flights, then finds return flights for all destinations
"""

import csv
import html, json, random, sys, time
from collections import defaultdict
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# Import destinations from gowild_fast
from gowild_fast import (
    create_session,
    destinations,
    get_flight_data,
)
# Import centralized configuration
from config import GOWILD_BLACKOUT_DATES


def is_blackout_date(date_str):
    """Check if a date is a GoWild blackout date"""
    return date_str in GOWILD_BLACKOUT_DATES


def search_outbound(origin, date_str, session):
    """Search all destinations from origin on a specific date"""
    print(f"\n{'='*60}")
    print(f"🛫 OUTBOUND: Searching from {origin} on {date_str}")
    print(f"{'='*60}")

    if is_blackout_date(date_str):
        print(f"🚫 BLACKOUT DATE - Skipping {date_str}")
        return {}

    results = {}
    total_dests = len(destinations)
    base_delay = 15

    print(f"\n🔍 Scanning {total_dests} destinations...\n")

    for idx, (dest_code, dest_name) in enumerate(destinations.items(), 1):
        delay = random.uniform(base_delay, base_delay + 10)

        print(f"[{idx}/{total_dests}] {origin}→{dest_code}", end=" ", flush=True)
        time.sleep(delay)

        formatted_date = (
            datetime.strptime(date_str, "%Y-%m-%d")
            .strftime("%b-%d,-%Y")
            .replace("-", "%20")
        )
        data, hit_limit = get_flight_data(origin, dest_code, formatted_date, session)

        if hit_limit:
            print("❌ Rate limit")
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
                            "flights": gowild,
                            "best_price": min(f.get("goWildFare", 999) for f in gowild),
                            "count": len(gowild),
                        }
                        print(
                            f"✅ {len(gowild)} flights (${results[dest_code]['best_price']:.2f})"
                        )
                    else:
                        print("○")
                else:
                    print("○")
            except (KeyError, IndexError, TypeError):
                print("○")
        else:
            print("○")

        if not hit_limit and base_delay > 15:
            base_delay = max(base_delay - 2, 15)

    print(f"\n✅ Found GoWild flights to {len(results)} destinations")
    return results


def search_return(destinations_list, return_date_str, session):
    """Search return flights from destinations to SFO"""
    print(f"\n{'='*60}")
    print(f"🛬 RETURN: Searching to SFO on {return_date_str}")
    print(f"{'='*60}")

    if is_blackout_date(return_date_str):
        print(f"🚫 BLACKOUT DATE - Skipping {return_date_str}")
        return {}

    results = {}
    total_dests = len(destinations_list)
    base_delay = 15

    print(f"\n🔍 Checking {total_dests} return routes...\n")

    for idx, dest_code in enumerate(destinations_list, 1):
        delay = random.uniform(base_delay, base_delay + 10)

        print(f"[{idx}/{total_dests}] {dest_code}→SFO", end=" ", flush=True)
        time.sleep(delay)

        formatted_date = (
            datetime.strptime(return_date_str, "%Y-%m-%d")
            .strftime("%b-%d,-%Y")
            .replace("-", "%20")
        )
        data, hit_limit = get_flight_data(dest_code, "SFO", formatted_date, session)

        if hit_limit:
            print("❌ Rate limit")
            base_delay = min(base_delay + 10, 60)
            continue

        if data and "journeys" in data:
            try:
                flights = data["journeys"][0].get("flights")
                if flights:
                    gowild = [f for f in flights if f.get("isGoWildFareEnabled")]
                    if gowild:
                        results[dest_code] = {
                            "flights": gowild,
                            "best_price": min(f.get("goWildFare", 999) for f in gowild),
                            "count": len(gowild),
                        }
                        print(
                            f"✅ {len(gowild)} flights (${results[dest_code]['best_price']:.2f})"
                        )
                    else:
                        print("○")
                else:
                    print("○")
            except (KeyError, IndexError, TypeError):
                print("○")
        else:
            print("○")

        if not hit_limit and base_delay > 15:
            base_delay = max(base_delay - 2, 15)

    print(f"\n✅ Found return flights from {len(results)} destinations")
    return results


def compile_roundtrips(outbound_by_date, return_by_date):
    """Compile all possible round-trip combinations"""
    roundtrips = []

    for out_date, out_dests in outbound_by_date.items():
        for dest_code, out_info in out_dests.items():
            dest_name = out_info["name"]

            for ret_date, ret_dests in return_by_date.items():
                if dest_code in ret_dests:
                    ret_info = ret_dests[dest_code]

                    # Calculate total price
                    total_price = out_info["best_price"] + ret_info["best_price"]

                    roundtrips.append(
                        {
                            "destination_code": dest_code,
                            "destination_name": dest_name,
                            "outbound_date": out_date,
                            "return_date": ret_date,
                            "outbound_price": out_info["best_price"],
                            "return_price": ret_info["best_price"],
                            "total_price": total_price,
                            "outbound_options": out_info["count"],
                            "return_options": ret_info["count"],
                        }
                    )

    return sorted(roundtrips, key=lambda x: x["total_price"])


def display_results(roundtrips):
    """Display round-trip results"""
    print(f"\n{'='*60}")
    print(f"ROUND-TRIP OPTIONS FOUND")
    print(f"{'='*60}\n")

    if not roundtrips:
        print("No round-trip combinations found 😔")
        return

    # Group by destination
    by_dest = defaultdict(list)
    for trip in roundtrips:
        by_dest[trip["destination_code"]].append(trip)

    print(
        f"Found {len(roundtrips)} round-trip combinations to {len(by_dest)} destinations\n"
    )

    for dest_code in sorted(by_dest.keys()):
        trips = by_dest[dest_code]
        dest_name = trips[0]["destination_name"]

        print(f"✈️  {dest_code} - {dest_name}")
        for trip in trips:
            print(f"   📅 {trip['outbound_date']} → {trip['return_date']}")
            print(
                f"      Out: ${trip['outbound_price']:.2f} ({trip['outbound_options']} options)"
            )
            print(
                f"      Return: ${trip['return_price']:.2f} ({trip['return_options']} options)"
            )
            print(f"      💰 Total: ${trip['total_price']:.2f}")
            print()


def highlight_best_deals(roundtrips, top_n=10):
    """Highlight the best deals"""
    print(f"\n{'='*60}")
    print(f"🏆 TOP {top_n} BEST DEALS (by total price)")
    print(f"{'='*60}\n")

    if not roundtrips:
        return

    for idx, trip in enumerate(roundtrips[:top_n], 1):
        days = (
            datetime.strptime(trip["return_date"], "%Y-%m-%d")
            - datetime.strptime(trip["outbound_date"], "%Y-%m-%d")
        ).days

        print(f"{idx}. {trip['destination_code']} - {trip['destination_name']}")
        print(
            f"   💰 ${trip['total_price']:.2f} total (${trip['outbound_price']:.2f} out + ${trip['return_price']:.2f} return)"
        )
        print(f"   📅 {trip['outbound_date']} → {trip['return_date']} ({days} days)")
        print(
            f"   ✈️  {trip['outbound_options']} outbound, {trip['return_options']} return flights"
        )
        print()


def export_results(roundtrips, filename="roundtrip_results.csv"):
    """Export results to CSV"""
    if not roundtrips:
        return

    with open(filename, "w", newline="") as csvfile:
        fieldnames = [
            "Destination_Code",
            "Destination_Name",
            "Outbound_Date",
            "Return_Date",
            "Trip_Days",
            "Outbound_Price",
            "Return_Price",
            "Total_Price",
            "Outbound_Options",
            "Return_Options",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for trip in roundtrips:
            days = (
                datetime.strptime(trip["return_date"], "%Y-%m-%d")
                - datetime.strptime(trip["outbound_date"], "%Y-%m-%d")
            ).days

            writer.writerow(
                {
                    "Destination_Code": trip["destination_code"],
                    "Destination_Name": trip["destination_name"],
                    "Outbound_Date": trip["outbound_date"],
                    "Return_Date": trip["return_date"],
                    "Trip_Days": days,
                    "Outbound_Price": trip["outbound_price"],
                    "Return_Price": trip["return_price"],
                    "Total_Price": trip["total_price"],
                    "Outbound_Options": trip["outbound_options"],
                    "Return_Options": trip["return_options"],
                }
            )

    print(f"✅ Results exported to {filename}")


if __name__ == "__main__":
    print("=== Round-Trip GoWild Flight Finder ===\n")

    # Configuration
    ORIGIN = "SFO"
    OUTBOUND_DATES = ["2025-12-11", "2025-12-12"]
    RETURN_DATES = ["2025-12-18", "2025-12-19", "2025-12-24"]

    print(f"🎯 Search Configuration:")
    print(f"   Origin: {ORIGIN}")
    print(f"   Outbound: {', '.join(OUTBOUND_DATES)}")
    print(f"   Return: {', '.join(RETURN_DATES)}")

    # Create session
    session = create_session()

    # Step 1: Search outbound flights
    outbound_results = {}
    for date in OUTBOUND_DATES:
        outbound_results[date] = search_outbound(ORIGIN, date, session)

    # Compile unique destinations with outbound flights
    all_destinations = set()
    for date_results in outbound_results.values():
        all_destinations.update(date_results.keys())

    print(f"\n{'='*60}")
    print(f"📊 OUTBOUND SUMMARY")
    print(f"{'='*60}")
    print(
        f"Total unique destinations with outbound GoWild flights: {len(all_destinations)}"
    )
    for date, results in outbound_results.items():
        print(f"  {date}: {len(results)} destinations")

    if not all_destinations:
        print("\n❌ No outbound flights found. Exiting.")
        sys.exit(1)

    # Step 2: Search return flights
    return_results = {}
    for date in RETURN_DATES:
        return_results[date] = search_return(list(all_destinations), date, session)

    print(f"\n{'='*60}")
    print(f"📊 RETURN SUMMARY")
    print(f"{'='*60}")
    for date, results in return_results.items():
        print(f"  {date}: {len(results)} destinations with return flights")

    # Step 3: Compile round-trips
    roundtrips = compile_roundtrips(outbound_results, return_results)

    # Step 4: Display results
    display_results(roundtrips)

    # Step 5: Highlight best deals
    highlight_best_deals(roundtrips, top_n=15)

    # Step 6: Export to CSV
    export_results(
        roundtrips, f"roundtrip_sfo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    print(f"\n{'='*60}")
    print(f"✅ Search complete! Found {len(roundtrips)} round-trip options")
    print(f"{'='*60}")
