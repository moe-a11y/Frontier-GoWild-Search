"""
Centralized Configuration for Frontier GoWild Search Tools
This file contains blackout dates and destination information used across all scripts.

Blackout dates source: https://www.flyfrontier.com/deals/gowild-pass/
Last updated: November 2025
"""

# ============================================================
# GOWILD BLACKOUT DATES
# ============================================================
# These dates are not available for GoWild Pass travel
# Source: https://www.flyfrontier.com/deals/gowild-pass/

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
    "2026-01-15",
    "2026-01-16",
    "2026-01-19",
    # February 2026
    "2026-02-12",
    "2026-02-13",
    "2026-02-16",
    # March 2026
    "2026-03-13",
    "2026-03-14",
    "2026-03-15",
    "2026-03-20",
    "2026-03-21",
    "2026-03-22",
    "2026-03-27",
    "2026-03-28",
    "2026-03-29",
    # April 2026
    "2026-04-03",
    "2026-04-04",
    "2026-04-05",
    "2026-04-06",
    "2026-04-10",
    "2026-04-11",
    "2026-04-12",
    # May 2026
    "2026-05-21",
    "2026-05-22",
    "2026-05-25",
    # June 2026
    "2026-06-25",
    "2026-06-26",
    "2026-06-27",
    "2026-06-28",
    # July 2026
    "2026-07-02",
    "2026-07-03",
    "2026-07-04",
    "2026-07-05",
    "2026-07-06",
    # September 2026
    "2026-09-03",
    "2026-09-04",
    "2026-09-07",
    # October 2026
    "2026-10-08",
    "2026-10-09",
    "2026-10-11",
    "2026-10-12",
    # November 2026
    "2026-11-24",
    "2026-11-25",
    "2026-11-28",
    "2026-11-29",
    "2026-11-30",
    # December 2026
    "2026-12-19",
    "2026-12-20",
    "2026-12-21",
    "2026-12-22",
    "2026-12-23",
    "2026-12-24",
    "2026-12-26",
    "2026-12-27",
    "2026-12-28",
    "2026-12-29",
    "2026-12-30",
    "2026-12-31",
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

# Combine all blackout dates into a single list
GOWILD_BLACKOUT_DATES = (
    GOWILD_BLACKOUT_DATES_2025 + GOWILD_BLACKOUT_DATES_2026 + GOWILD_BLACKOUT_DATES_2027
)

# ============================================================
# ORIGIN AIRPORTS
# ============================================================
# Bay Area origins to check. Both are nearby, so we cover both.

ORIGINS = ["SFO", "SJC"]

# ============================================================
# DESTINATIONS TO CHECK FOR DEALS
# ============================================================
# Curated list of destinations to check for GoWild / Discount Den deals.
# Split by international vs domestic (CONUS) because they use different
# booking windows in the scheduled deal checker:
#   - Domestic (CONUS): check the NEXT day
#   - International / non-CONUS: check 10 days out
# Verify current routes on flyfrontier.com.

# International / non-CONUS (includes Puerto Rico territories)
INTERNATIONAL_DESTINATIONS = {
    "CUN": "Cancun, MX",
    "PVR": "Puerto Vallarta, MX",
    "GUA": "Guatemala City, GT",
    "SAL": "San Salvador, El Salvador",
    "SJO": "San Jose, Costa Rica",
    "MBJ": "Montego Bay, Jamaica",
    "SDQ": "Santo Domingo, DR",
    "PUJ": "Punta Cana, DR",
    "STI": "Santiago, DR",
    "BQN": "Aguadilla, PR",
    "SJU": "San Juan, PR",
    "SXM": "St. Maarten",
}

# Domestic (CONUS)
DOMESTIC_DESTINATIONS = {
    "LAS": "Las Vegas, NV",
    "SLC": "Salt Lake City, UT",
    "CLE": "Cleveland, OH",
    "TYS": "Knoxville, TN",
    "ORD": "Chicago O'Hare, IL",
    "DEN": "Denver, CO",
    "PHL": "Philadelphia, PA",
    "RDU": "Raleigh-Durham, NC",
    "ONT": "Ontario, CA",
    "MIA": "Miami, FL",
    "FLL": "Fort Lauderdale, FL",
    "PBI": "West Palm Beach, FL",
    "BNA": "Nashville, TN",
    "MSY": "New Orleans, LA",
    "BOI": "Boise, ID",
    "GEG": "Spokane, WA",
}

# Combined list (international first), used by the single-shot browser scripts.
SFO_DIRECT_DESTINATIONS = {**INTERNATIONAL_DESTINATIONS, **DOMESTIC_DESTINATIONS}

# ============================================================
# HELPER FUNCTIONS
# ============================================================


def is_blackout_date(date_str):
    """
    Check if a date is a GoWild blackout date.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        bool: True if date is a blackout date, False otherwise
    """
    return date_str in GOWILD_BLACKOUT_DATES


def get_destination_name(code):
    """
    Get the full name of a destination from its airport code.

    Args:
        code: 3-letter airport code (e.g., 'DEN')

    Returns:
        str: Full destination name, or the code itself if not found
    """
    return SFO_DIRECT_DESTINATIONS.get(code.upper(), code)


def get_all_destination_codes():
    """
    Get a list of all SFO direct destination codes.

    Returns:
        list: List of 3-letter airport codes
    """
    return list(SFO_DIRECT_DESTINATIONS.keys())
