#!/usr/bin/env python3
"""
Fast Round-trip GoWild flight finder
Searches popular destinations only for quick results
"""

import csv
import html, json, random, sys, time
from collections import defaultdict
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# Import from gowild_fast
from gowild_fast import create_session, get_flight_data, GOWILD_BLACKOUT_DATES

# Popular/likely destinations from SFO
POPULAR_DESTINATIONS = {
    # Major hubs
    "DEN": "Denver",
    "LAS": "Las Vegas",
    "PHX": "Phoenix",
    "ATL": "Atlanta",
    # California
    "LAX": "Los Angeles",
    "SAN": "San Diego",
    "ONT": "Ontario, CA",
    "SNA": "Orange County",
    # Southwest USA
    "SLC": "Salt Lake City",
    "AUS": "Austin",
    "DAL": "Dallas",
    # Florida
    "MIA": "Miami",
    "FLL": "Fort Lauderdale",
    "MCO": "Orlando",
    "TPA": "Tampa",
    # Mexico/Caribbean
    "CUN": "Cancun",
    "SJD": "Los Cabos",
    "PVR": "Puerto Vallarta",
    "PUJ": "Punta Cana, DR",
    # Other Popular
    "SEA": "Seattle",
    "PDX": "Portland, OR",
    "ORD": "Chicago",
    "JFK": "New York JFK",
    "BOS": "Boston",
}


def is_blackout_date(date_str):
    """Check if a date is a GoWild blackout date"""
    return date_str in GOWILD_BLACKOUT_DATES


def search_outbound(origin, date_str, destinations, session):
    """Search specified destinations from origin on a specific date"""
    print(f"\n{'='*70}")
    print(f"🛫 OUTBOUND: {origin} on {date_str}")
    print(f"{'='*70}")

    if is_blackout_date(date_str):
        print(f"🚫 BLACKOUT DATE - Skipping {date_str}")
        return {}

    results = {}
    total_dests = len(destinations)
    base_delay = 15

    print(f"\n🔍 Scanning {total_dests} popular destinations...\n")

    for idx, (dest_code, dest_name) in enumerate(destinations.items(), 1):
        delay = random.uniform(base_delay, base_delay + 10)

        print(
            f"[{idx}/{total_dests}] {origin}→{dest_code} ({dest_name[:20]})",
            end=" ",
            flush=True,
        )
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
                            f"✅ {len(gowild)} (${results[dest_code]['best_price']:.2f})"
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


def search_return(destinations_list, dest_names, return_date_str, session):
    """Search return flights from destinations to SFO"""
    print(f"\n{'='*70}")
    print(f"🛬 RETURN: To SFO on {return_date_str}")
    print(f"{'='*70}")

    if is_blackout_date(return_date_str):
        print(f"🚫 BLACKOUT DATE - Skipping {return_date_str}")
        return {}

    results = {}
    total_dests = len(destinations_list)
    base_delay = 15

    print(f"\n🔍 Checking {total_dests} return routes...\n")

    for idx, dest_code in enumerate(destinations_list, 1):
        delay = random.uniform(base_delay, base_delay + 10)

        dest_name = dest_names.get(dest_code, "Unknown")
        print(
            f"[{idx}/{total_dests}] {dest_code}→SFO ({dest_name[:20]})",
            end=" ",
            flush=True,
        )
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
                            f"✅ {len(gowild)} (${results[dest_code]['best_price']:.2f})"
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

                    # Calculate trip days
                    days = (
                        datetime.strptime(ret_date, "%Y-%m-%d")
                        - datetime.strptime(out_date, "%Y-%m-%d")
                    ).days

                    roundtrips.append(
                        {
                            "destination_code": dest_code,
                            "destination_name": dest_name,
                            "outbound_date": out_date,
                            "return_date": ret_date,
                            "trip_days": days,
                            "outbound_price": out_info["best_price"],
                            "return_price": ret_info["best_price"],
                            "total_price": total_price,
                            "outbound_options": out_info["count"],
                            "return_options": ret_info["count"],
                        }
                    )

    return sorted(roundtrips, key=lambda x: x["total_price"])


def display_full_results(roundtrips):
    """Display all round-trip results grouped by destination"""
    print(f"\n{'='*70}")
    print(f"📋 ALL ROUND-TRIP OPTIONS")
    print(f"{'='*70}\n")

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
            print(
                f"   📅 {trip['outbound_date']} → {trip['return_date']} ({trip['trip_days']} days)"
            )
            print(
                f"      Out: ${trip['outbound_price']:.2f} | Return: ${trip['return_price']:.2f} | Total: ${trip['total_price']:.2f}"
            )
            print(
                f"      ({trip['outbound_options']} outbound, {trip['return_options']} return flights)"
            )
        print()


def highlight_best_deals(roundtrips, top_n=15):
    """Highlight the best deals"""
    print(f"\n{'='*70}")
    print(f"🏆 TOP {top_n} BEST DEALS (Sorted by Total Price)")
    print(f"{'='*70}\n")

    if not roundtrips:
        return

    for idx, trip in enumerate(roundtrips[:top_n], 1):
        print(f"{idx}. {trip['destination_code']} - {trip['destination_name']}")
        print(
            f"   💰 ${trip['total_price']:.2f} total (${trip['outbound_price']:.2f} + ${trip['return_price']:.2f})"
        )
        print(
            f"   📅 {trip['outbound_date']} → {trip['return_date']} ({trip['trip_days']} days)"
        )
        print(
            f"   ✈️  {trip['outbound_options']} outbound, {trip['return_options']} return options"
        )
        print()


def export_results(roundtrips, filename):
    """Export results to CSV"""
    if not roundtrips:
        print("No results to export")
        return

    with open(filename, "w", newline="") as csvfile:
        fieldnames = [
            "Rank",
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

        for idx, trip in enumerate(roundtrips, 1):
            writer.writerow(
                {
                    "Rank": idx,
                    "Destination_Code": trip["destination_code"],
                    "Destination_Name": trip["destination_name"],
                    "Outbound_Date": trip["outbound_date"],
                    "Return_Date": trip["return_date"],
                    "Trip_Days": trip["trip_days"],
                    "Outbound_Price": f"${trip['outbound_price']:.2f}",
                    "Return_Price": f"${trip['return_price']:.2f}",
                    "Total_Price": f"${trip['total_price']:.2f}",
                    "Outbound_Options": trip["outbound_options"],
                    "Return_Options": trip["return_options"],
                }
            )

    print(f"\n✅ Full results exported to: {filename}")


if __name__ == "__main__":
    print("=" * 70)
    print(" 🎯 FAST ROUND-TRIP GOWILD FINDER")
    print("=" * 70)
    print()

    # Configuration
    ORIGIN = "SFO"
    OUTBOUND_DATES = ["2025-12-11", "2025-12-12"]
    RETURN_DATES = ["2025-12-18", "2025-12-19", "2025-12-24"]

    print(f"📍 Origin: {ORIGIN}")
    print(f"🛫 Outbound dates: {', '.join(OUTBOUND_DATES)}")
    print(f"🛬 Return dates: {', '.join(RETURN_DATES)}")
    print(f"🎯 Searching {len(POPULAR_DESTINATIONS)} popular destinations")
    print()

    # Create session
    session = create_session()

    # Step 1: Search outbound flights
    print("\n" + "=" * 70)
    print("PHASE 1: OUTBOUND FLIGHTS")
    print("=" * 70)

    outbound_results = {}
    for date in OUTBOUND_DATES:
        outbound_results[date] = search_outbound(
            ORIGIN, date, POPULAR_DESTINATIONS, session
        )

    # Compile unique destinations with outbound flights
    all_destinations = {}
    for date_results in outbound_results.values():
        for code, info in date_results.items():
            all_destinations[code] = info["name"]

    print(f"\n{'='*70}")
    print(f"📊 OUTBOUND SUMMARY")
    print(f"{'='*70}")
    print(
        f"✅ {len(all_destinations)} unique destinations with outbound GoWild flights"
    )
    for date, results in outbound_results.items():
        print(f"   {date}: {len(results)} destinations")
    print()

    if not all_destinations:
        print("\n❌ No outbound flights found. Exiting.")
        sys.exit(1)

    # Step 2: Search return flights
    print("\n" + "=" * 70)
    print("PHASE 2: RETURN FLIGHTS")
    print("=" * 70)

    return_results = {}
    for date in RETURN_DATES:
        return_results[date] = search_return(
            list(all_destinations.keys()), all_destinations, date, session
        )

    print(f"\n{'='*70}")
    print(f"📊 RETURN SUMMARY")
    print(f"{'='*70}")
    for date, results in return_results.items():
        print(f"   {date}: {len(results)} destinations with return flights")
    print()

    # Step 3: Compile round-trips
    roundtrips = compile_roundtrips(outbound_results, return_results)

    # Step 4: Display all results
    display_full_results(roundtrips)

    # Step 5: Highlight best deals
    highlight_best_deals(roundtrips, top_n=15)

    # Step 6: Export to CSV
    filename = f"roundtrip_sfo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    export_results(roundtrips, filename)

    print(f"\n{'='*70}")
    print(f"✅ SEARCH COMPLETE")
    print(f"{'='*70}")
    print(f"📊 Total combinations: {len(roundtrips)}")
    print(f"🎯 Destinations: {len(set(r['destination_code'] for r in roundtrips))}")
    if roundtrips:
        print(
            f"💰 Best deal: ${roundtrips[0]['total_price']:.2f} to {roundtrips[0]['destination_code']}"
        )
    print(f"📁 Results saved to: {filename}")
    print("=" * 70)
