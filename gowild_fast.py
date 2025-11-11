#!/usr/bin/env python3
"""
Optimized GoWild scraper using requests with smart rate limiting
This version is MUCH faster than Selenium but requires careful rate limiting
"""

import csv
import html, json, random, time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

# Global Variables
destinations_avail = {}

# Frontier GoWild Blackout Dates
# Updated from: https://www.flyfrontier.com/deals/gowild-pass/
# Last updated: November 2025
GOWILD_BLACKOUT_DATES_2025 = [
    # October 2025
    "2025-10-09",
    "2025-10-10",
    "2025-10-12",
    "2025-10-13",
    # November 2025 (Thanksgiving week)
    "2025-11-25",
    "2025-11-26",
    "2025-11-29",
    "2025-11-30",
    # December 2025 (Christmas/New Year)
    "2025-12-01",
    "2025-12-20",
    "2025-12-21",
    "2025-12-22",
    "2025-12-23",
    "2025-12-26",
    "2025-12-27",
    "2025-12-28",
    "2025-12-29",
    "2025-12-30",
    "2025-12-31",
]

GOWILD_BLACKOUT_DATES_2026 = [
    # January 2026
    "2026-01-01",
    "2026-01-03",
    "2026-01-04",
]

GOWILD_BLACKOUT_DATES_2027 = [
    # January 2027
    "2027-01-01",
    "2027-01-02",
    "2027-01-03",
    "2027-01-14",
    "2027-01-15",
    "2027-01-18",
    # February 2027
    "2027-02-11",
    "2027-02-12",
    "2027-02-15",
    # March 2027
    "2027-03-12",
    "2027-03-13",
    "2027-03-14",
    "2027-03-19",
    "2027-03-20",
    "2027-03-21",
    "2027-03-26",
    "2027-03-27",
    "2027-03-28",
    "2027-03-29",
    # April 2027
    "2027-04-02",
    "2027-04-03",
    "2027-04-04",
]

# Combine all blackout dates
GOWILD_BLACKOUT_DATES = (
    GOWILD_BLACKOUT_DATES_2025 + GOWILD_BLACKOUT_DATES_2026 + GOWILD_BLACKOUT_DATES_2027
)

# Updated November 2025 - Frontier Airlines Destinations
# Note: This list is validated by actual flight searches
# Airports consistently returning "No data" should be investigated/removed

destinations = {
    # Caribbean & Central America
    "ANU": "Antigua and Barbuda",
    "NAS": "Nassau, Bahamas",
    "BZE": "Belize City",
    "LIR": "Liberia, Costa Rica",
    "SJO": "San José, Costa Rica",
    "PUJ": "Punta Cana, DR",
    "SDQ": "Santo Domingo, DR",
    "SAL": "San Salvador, El Salvador",
    "GUA": "Guatemala City",
    "KIN": "Kingston, Jamaica",
    "MBJ": "Montego Bay, Jamaica",
    "SXM": "St. Maarten",
    "STT": "St. Thomas, USVI",
    # Mexico
    "SJD": "Los Cabos",
    "GDL": "Guadalajara",
    "PVR": "Puerto Vallarta",
    "MTY": "Monterrey",
    "CUN": "Cancun",
    "CZM": "Cozumel",
    "MEX": "Mexico City",  # Added - major hub
    # Southwest USA
    "PHX": "Phoenix",
    "TUS": "Tucson",  # Added - Frontier serves
    "LAS": "Las Vegas",
    "SAN": "San Diego",
    "ONT": "Ontario, CA",
    "SNA": "Orange County",
    "OAK": "Oakland",
    "SMF": "Sacramento",
    "SFO": "San Francisco",
    "SJC": "San Jose, CA",  # Added - major CA airport
    # Mountain West
    "DEN": "Denver",
    "SLC": "Salt Lake City",
    "BOI": "Boise",  # Added - Frontier serves
    # Texas
    "AUS": "Austin",
    "DFW": "Dallas/Fort Worth",
    "ELP": "El Paso",
    "IAH": "Houston",
    "SAT": "San Antonio",
    "DAL": "Dallas Love Field",  # Added - alternative DFW
    # Midwest
    "ORD": "Chicago O'Hare",
    "MDW": "Chicago Midway",
    "DSM": "Des Moines",
    "OMA": "Omaha",
    "MCI": "Kansas City",
    "STL": "St. Louis",
    "MSP": "Minneapolis",
    "DTW": "Detroit",
    "CLE": "Cleveland",
    "CMH": "Columbus, OH",
    "IND": "Indianapolis",
    "MKE": "Milwaukee",
    "GRR": "Grand Rapids",
    "CID": "Cedar Rapids",
    "BMI": "Bloomington, IL",
    "FAR": "Fargo",
    "MSN": "Madison",
    # South
    "ATL": "Atlanta",
    "BNA": "Nashville",
    "MEM": "Memphis",
    "MSY": "New Orleans",
    "BHM": "Birmingham",  # Added - Frontier serves
    "JAX": "Jacksonville",
    "TPA": "Tampa",
    "MCO": "Orlando",
    "MIA": "Miami",
    "FLL": "Fort Lauderdale",
    "PBI": "West Palm Beach",
    "RSW": "Fort Myers",
    "SRQ": "Sarasota",
    "PNS": "Pensacola",
    "SAV": "Savannah",
    "CHS": "Charleston, SC",
    "MYR": "Myrtle Beach",
    "CLT": "Charlotte",
    "RDU": "Raleigh-Durham",
    "TYS": "Knoxville",
    # Northeast
    "BOS": "Boston",
    "BDL": "Hartford",
    "PWM": "Portland, ME",
    "PHL": "Philadelphia",
    "PIT": "Pittsburgh",
    "BWI": "Baltimore",
    "DCA": "Washington DC",
    "ORF": "Norfolk",
    "BUF": "Buffalo",
    "SYR": "Syracuse",
    "LGA": "New York LaGuardia",
    "EWR": "Newark",  # Added - major NYC airport
    "ISP": "Long Island",
    "SWF": "Newburgh",
    "TTN": "Trenton",
    "MDT": "Harrisburg",
    # Northwest
    "SEA": "Seattle",
    "PDX": "Portland, OR",
    "GEG": "Spokane",  # Added - Frontier serves
    # Arkansas
    "XNA": "Northwest Arkansas",
    "LIT": "Little Rock",
    # New Mexico
    "ABQ": "Albuquerque",  # Added - major NM hub
    # Nebraska
    "LNK": "Lincoln",  # Added - Frontier serves
    # Montana
    "MSO": "Missoula",
    "BIL": "Billings",  # Added - Frontier serves
    # Oklahoma
    "OKC": "Oklahoma City",
    "TUL": "Tulsa",  # Added - Frontier serves
    # Kentucky
    "CVG": "Cincinnati/Kentucky",
    "SDF": "Louisville",  # Added - Frontier serves
    # Puerto Rico
    "SJU": "San Juan",
    "BQN": "Aguadilla",
    "PSE": "Ponce",
}


def create_session():
    """Create a session that mimics a real browser"""
    session = requests.Session()

    # Realistic headers
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
    )

    # First, visit the main site to get cookies
    print("Establishing session with Frontier...")
    try:
        session.get("https://www.flyfrontier.com/", timeout=15)
        time.sleep(2)
        print("✅ Session established")
    except Exception as e:
        print(f"⚠️  Warning: {e}")

    return session


def get_flight_data(origin, dest, date, session):
    """Get flight data for a single route"""
    url = f"https://booking.flyfrontier.com/Flight/InternalSelect?o1={origin}&d1={dest}&dd1={date}&ADT=1&mon=true&promo="

    try:
        response = session.get(url, timeout=15)

        if response.status_code == 403:
            print("⚠️  CAPTCHA triggered - slowing down...")
            return None, True  # True = hit rate limit

        if response.status_code != 200:
            return None, False

        # Check for CAPTCHA in content
        if "px-captcha" in response.text or len(response.text) < 10000:
            return None, True

        # Extract flight data
        soup = BeautifulSoup(response.text, "html.parser")

        # Look for the specific script with flight data
        # The data is in a variable assignment like: var .... = {...};
        for script in soup.find_all("script"):
            script_text = script.string
            if script_text and "journeys" in script_text and "flights" in script_text:
                try:
                    # Find JSON-like data
                    decoded_data = html.unescape(script_text)

                    # Extract JSON between { and };
                    start = decoded_data.find("{")
                    if start == -1:
                        continue

                    # Find the matching closing brace followed by semicolon
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

    # Start with longer delay
    base_delay = 15  # seconds

    for idx, (dest_code, dest_name) in enumerate(destinations.items(), 1):
        # Smart delay - increases if we hit rate limits
        delay = random.uniform(base_delay, base_delay + 10)

        print(
            f"[{idx}/{len(destinations)}] {origin} → {dest_code} ({dest_name})", end=" "
        )
        print(f"(waiting {delay:.1f}s)...", end=" ", flush=True)

        time.sleep(delay)

        data, hit_limit = get_flight_data(origin, dest_code, date, session)

        if hit_limit:
            print("❌ Rate limited - increasing delay")
            base_delay = min(base_delay + 10, 60)  # Cap at 60 seconds
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

        # Reduce delay if things are going well
        if not hit_limit and base_delay > 15:
            base_delay = max(base_delay - 2, 15)

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

        for flight in info["flights"][:3]:  # Show first 3
            print(
                f"   • ${flight.get('goWildFare')} - {flight.get('stopsText')} - {flight.get('duration')}"
            )

        print()


def parse_date(date_str):
    """Parse date string in various formats (YYYY-MM-DD, MM/DD/YYYY, etc.)"""
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD or MM/DD/YYYY")


def get_destinations_to_search():
    """Allow user to specify specific destinations or search all"""
    print("\nDestination Selection:")
    print("  1. Search all destinations")
    print("  2. Specify specific destination airports")
    choice = input("Choose option (1 or 2): ").strip()

    if choice == "1":
        return destinations
    elif choice == "2":
        print(
            "\nEnter destination airport codes separated by commas (e.g., LAX,JFK,ORD)"
        )
        print("Available airports (sample):")
        # Show sample airports
        sample = list(destinations.items())[:10]
        for code, name in sample:
            print(f"  {code}: {name}")
        print(f"  ... and {len(destinations) - 10} more")

        dest_input = input("\nDestination codes: ").upper()
        selected_codes = [code.strip() for code in dest_input.split(",")]

        # Validate and filter destinations
        valid_dests = {}
        for code in selected_codes:
            if code in destinations:
                valid_dests[code] = destinations[code]
            else:
                print(f"Warning: {code} not found in destination list")

        if not valid_dests:
            print("No valid destinations selected. Using all destinations.")
            return destinations

        print(f"\nSearching {len(valid_dests)} destination(s):")
        for code, name in valid_dests.items():
            print(f"  {code}: {name}")
        return valid_dests
    else:
        print("Invalid choice. Using all destinations.")
        return destinations


def is_blackout_date(date_obj):
    """Check if a date is a GoWild blackout date"""
    date_str = date_obj.strftime("%Y-%m-%d")
    return date_str in GOWILD_BLACKOUT_DATES


if __name__ == "__main__":
    print("=== Frontier GoWild Flight Search (Fast) ===\n")

    origin = input("Origin airport code (e.g., SFO): ").upper()

    print("\nDate Selection:")
    print("  1. Today")
    print("  2. Tomorrow")
    print("  3. Both (Today and Tomorrow)")
    print("  4. Date range")
    print("  0. Exit")
    input_dates = input("Choose option: ").strip()

    if input_dates == "0":
        exit()

    today = datetime.today()
    dates_to_search = []

    # Process date selection first
    if input_dates == "1":
        dates_to_search.append(today)
    elif input_dates == "2":
        dates_to_search.append(today + timedelta(days=1))
    elif input_dates == "3":
        dates_to_search.append(today)
        dates_to_search.append(today + timedelta(days=1))
    elif input_dates == "4":
        # Date range option
        print("\nEnter dates in YYYY-MM-DD or MM/DD/YYYY format")
        start_date_str = input("Start date: ").strip()
        end_date_str = input("End date: ").strip()

        try:
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)

            if start_date > end_date:
                print("Error: Start date must be before or equal to end date")
                exit()

            # Generate all dates in range
            current_date = start_date
            while current_date <= end_date:
                dates_to_search.append(current_date)
                current_date += timedelta(days=1)

            print(
                f"\nSearching {len(dates_to_search)} dates from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            )
        except ValueError as e:
            print(f"Error: {e}")
            exit()
    else:
        print("Invalid option")
        exit()

    # Get destinations to search AFTER date processing
    destinations_to_search = get_destinations_to_search()

    # Search flights for all dates
    all_results = {}
    blackout_dates = []

    for date_obj in dates_to_search:
        # Check if this is a blackout date
        if is_blackout_date(date_obj):
            blackout_dates.append(date_obj)
            print(f"\n{'='*60}")
            print(f"🚫 BLACKOUT DATE: {date_obj.strftime('%A, %B %d, %Y')}")
            print(f"{'='*60}")
            print("❌ This is a GoWild blackout date - no GoWild flights available.")
            print("   Skipping search for this date.")
            print(f"{'='*60}")
            all_results[date_obj.strftime("%Y-%m-%d")] = {}
            continue

        date_str = date_obj.strftime("%b-%d,-%Y").replace("-", "%20")
        print(f"\n{'='*60}")
        print(f"Searching flights for {date_obj.strftime('%A, %B %d, %Y')}")
        print(f"{'='*60}")

        results = scan_routes(origin, destinations_to_search, date_str)
        display_results(origin, results)

        print(f"\n{'='*60}")
        print(f"Total destinations with GoWild flights: {len(results)}")
        print(f"{'='*60}")

        # Export to CSV
        if results:
            export_to_csv(origin, results, date_str)

        # Store results for this date
        all_results[date_obj.strftime("%Y-%m-%d")] = results

    # Summary across all dates
    if len(dates_to_search) > 1:
        print(f"\n\n{'='*60}")
        print("SUMMARY ACROSS ALL DATES")
        print(f"{'='*60}")

        # Show blackout dates first if any
        if blackout_dates:
            print(f"\n🚫 Blackout Dates ({len(blackout_dates)}):")
            for bd in blackout_dates:
                print(f"   {bd.strftime('%Y-%m-%d (%A)')}: GoWild not available")

        # Show search results
        searchable_dates = [d for d in dates_to_search if d not in blackout_dates]
        if searchable_dates:
            print(f"\n✅ Searched Dates ({len(searchable_dates)}):")
            for date_key, results in all_results.items():
                if results:  # Only show if not empty (not a blackout)
                    # Check if this was a blackout (empty dict)
                    date_obj_check = datetime.strptime(date_key, "%Y-%m-%d")
                    if date_obj_check not in blackout_dates:
                        print(
                            f"   {date_key}: {len(results)} destinations with GoWild flights"
                        )
