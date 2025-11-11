import html, json, random, time
from datetime import datetime, timedelta

import undetected_chromedriver as uc

from bs4 import BeautifulSoup

# TODO
# Speed up processing time
# Better UI
# Do not parse airports where flights are not offered
# Multi-processing ?

# Global Variables
destination_count = 0
destinations_avail = {}

destinations = {
    "ANU": "Antigua and Barbuda",
    "NAS": "Bahamas",
    "BZE": "Belize",
    "LIR": "Costa Rica",
    "SJO": "San José",
    "PUJ": "Punta Cana, DR",
    "SDQ": "Santo Domingo, DR",
    "SAL": "El Salvador",
    "GUA": "Guatemala",
    "KIN": "Jamaica",
    "MBJ": "St. James",
    "SJD": "Los Cabos, MX",
    "GDL": "Guadalajara, MX",
    "PVR": "Puerto Vallarta, MX",
    "MTY": "Monetrrey, MX",
    "CUN": "Cancun, MX",
    "CZM": "Cozumel, MX",
    "SXM": "St. Maarten",
    "PHX": "Phoenix",
    "XNA": "Arkansas",
    "LIT": "Little Rock, AR",
    "OAK": "Oakland",
    "ONT": "Ontario",
    "SNA": "Orange County",
    "SMF": "Sacramento",
    "SAN": "San Diego",
    "SFO": "San Francisco",
    "DEN": "Colorado",
    "BDL": "Connecticut",
    "FLL": "Fort Lauderdale, FL",
    "RSW": "Fort Myers, FL",
    "JAX": "Jacksonville, FL",
    "MIA": "Miami, FL",
    "MCO": "Orlando, FL",
    "PNS": "Pensacola, FL",
    "SRQ": "Sarasota, FL",
    "TPA": "Tampa, FL",
    "PBI": "West Palm Beach, FL",
    "ATL": "Atlanta, Georgia",
    "SAV": "Savannah, Georgia",
    "BMI": "Illinois",
    "MDW": "Chicago",
    "IND": "Indiana",
    "CID": "Cedar rapids, Iowa",
    "DSM": "Des Moines, Iowa",
    "CVG": "Kentucky",
    "MSY": "Louisiana",
    "PWM": "Maine",
    "BWI": "Maryland",
    "BOS": "Massachusetts",
    "DTW": "Michigan",
    "GRR": "Grand Rapids, MI",
    "MSP": "Minnesota",
    "MCI": "Missouri",
    "STL": "St. Louis",
    "MSO": "Montana",
    "OMA": "Nebraska",
    "LAS": "Las Vegas",
    "TTN": "New Jersey",
    "BUF": "New York",
    "ISP": "Long Island/Islip",
    "SWF": "Newburgh",
    "LGA": "New York City",
    "SYR": "Syracuse",
    "CLT": "North Carolina",
    "RDU": "Raleigh, NC",
    "FAR": "North Dakota",
    "CLE": "Ohio",
    "CMH": "Columbus",
    "OKC": "Oklahoma",
    "PDX": "Oregon",
    "MDT": "Pennsylvania",
    "PHL": "Philadelphia",
    "PIT": "Pittsburgh",
    "BQN": "Aguadilla, Puerto Rico",
    "PSE": "Ponce, Puerto Rico",
    "SJU": "San Juan, Puerto Rico",
    "CHS": "Charleston, South Carolina",
    "MYR": "Myrtle Beach, SC",
    "TYS": "Tennessee",
    "MEM": "Memphis",
    "BNA": "Nashville",
    "AUS": "Austin, Texas",
    "DFW": "Dallas/Fort Worth",
    "ELP": "El Paso",
    "IAH": "Houston",
    "SAT": "San Antonio",
    "STT": "U.S. Virgin Islands",
    "SLC": "Utah",
    "DCA": "Virginia",
    "ORF": "Norfolk",
    "SEA": "Washington",
    "GRB": "Wisconsin",
    "MSN": "Madison",
    "MKE": "Milwaukee",
}


def create_driver():
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")

    # Create undetected Chrome driver
    driver = uc.Chrome(
        options=options,
        use_subprocess=True,
        version_main=None,  # Auto-detect Chrome version
    )

    return driver


def get_flight_html(origin, destinations, date, driver):
    f = open("destinations.txt", "a")
    f.write("Origin: " + origin + "\n")
    print(f"Processing {len(destinations)} destinations from {origin}...")
    for idx, dest in enumerate(destinations.keys(), 1):
        delay = random.uniform(3, 6)
        print(
            f"[{idx}/{len(destinations)}] Checking {origin} to {dest} (waiting {delay:.1f}s)...",
            end=" ",
        )
        time.sleep(delay)
        url = f"https://booking.flyfrontier.com/Flight/InternalSelect?o1={origin}&d1={dest}&dd1={date}&ADT=1&mon=true&promo="

        try:
            # Check if driver window is still open
            if not driver.window_handles:
                print("Browser window closed!")
                break

            driver.get(url)
            time.sleep(3)  # Increased wait time
            page_source = driver.page_source

            decoded_data = extract_html_from_source(page_source)
            if decoded_data is not None:
                print("✓")
                extract_json(decoded_data, origin, dest, date)
                f.write(dest + ",")
            else:
                print("No data found")
        except Exception as e:
            print(f"Error: {type(e).__name__}")
            # If it's a window closed error, break the loop
            if "no such window" in str(e) or "target window already closed" in str(e):
                print("Browser window was closed. Stopping.")
                break
            continue
    f.close()


def extract_html_from_source(page_source):
    try:
        soup = BeautifulSoup(page_source, "html.parser")
        scripts = soup.find("script", type="text/javascript")
        if scripts:
            decoded_data = html.unescape(scripts.text)
            decoded_data = decoded_data[
                decoded_data.index("{") : decoded_data.index(";") - 1
            ]
            return json.loads(decoded_data)
    except Exception as e:
        return None
    return None


def extract_json(flight_data, origin, dest, date):
    # Extract the flights with isGoWildFareEnabled as true
    try:
        flights = flight_data["journeys"][0]["flights"]
    except (TypeError, KeyError):
        return
    if flights == None:
        return
    go_wild_count = 0

    for flight in flights:
        if flight["isGoWildFareEnabled"]:
            if go_wild_count == 0:
                print(f"\n{origin} to {dest}: {destinations[dest]} available:")
            go_wild_count += 1
            info = flight["legs"][0]
            print(f"flight {go_wild_count}. {flight['stopsText']}")
            print(f"\tDate: {info['departureDate'][5:10]}")
            print(f"\tDepart: {info['departureDateFormatted']}")
            print(f"\tTotal flight time: {flight['duration']}")
            print(f"Price: ${flight['goWildFare']}")
            # if go wild seats value is provided
            if flight["goWildFareSeatsRemaining"] is not None:
                print(f"Go Wild: {flight['goWildFareSeatsRemaining']}\n")
    if go_wild_count != 0:
        destinations_avail[dest] = destinations.get(dest)
        print(
            f"{origin} to {dest}: {go_wild_count} Go Wild flights available for {date.replace('%20', ' ')}"
        )
    else:
        print(f"No flights from {origin} to {dest}")
    return


def extract_html(response):
    # Parse the HTML source using BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")

    # Find all <script> tags with type="text/javascript" and extract their contents
    scripts = soup.find("script", type="text/javascript")
    decoded_data = html.unescape(scripts.text)
    decoded_data = decoded_data[decoded_data.index("{") : decoded_data.index(";") - 1]
    return json.loads(decoded_data)


def print_dests(origin):
    print(f"\n{len(destinations_avail)} destinations found from {origin}:")
    for dest, name in destinations_avail.items():
        print(f"{dest}: {name}")


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
        print("Available airports:")
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


def main():
    global destinations, destinations_avail

    print("=== Frontier GoWild Flight Search ===\n")

    origin = input("Origin IATA airport code: ").upper()

    print("\nDate Selection:")
    print("  1. Today")
    print("  2. Tomorrow")
    print("  3. Both (Today and Tomorrow)")
    print("  4. Date range")
    print("  0. Exit")
    input_dates = input("Choose option: ").strip()

    if input_dates == "0":
        return

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
                return

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
            return
    else:
        print("Invalid option")
        return

    # Get destinations to search AFTER date processing
    destinations_to_search = get_destinations_to_search()

    driver = None
    try:
        driver = create_driver()

        # Search flights for all dates
        for date_obj in dates_to_search:
            destinations_avail = {}  # Reset for each date
            travel_date = date_obj.strftime("%b-%d,-%Y").replace("-", "%20")
            print(f"\n{'='*60}")
            print(f"Searching flights for {date_obj.strftime('%A, %B %d, %Y')}")
            print(f"{'='*60}")
            get_flight_html(origin, destinations_to_search, travel_date, driver)
            print_dests(origin)
    except KeyboardInterrupt:
        print("\n\nSearch interrupted by user.")
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
