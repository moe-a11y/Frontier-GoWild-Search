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
    GOWILD_BLACKOUT_DATES_2025 + 
    GOWILD_BLACKOUT_DATES_2026 + 
    GOWILD_BLACKOUT_DATES_2027
)

# ============================================================
# SFO DIRECT DESTINATIONS
# ============================================================
# Frontier Airlines direct destinations from San Francisco (SFO)
# Based on Frontier route network - verify current routes on flyfrontier.com

SFO_DIRECT_DESTINATIONS = {
    # Major Frontier Hubs
    "DEN": "Denver",
    "LAS": "Las Vegas",
    "PHX": "Phoenix",
    "ATL": "Atlanta",
    "ORD": "Chicago O'Hare",
    "DFW": "Dallas/Fort Worth",
    
    # Southwest/West Coast
    "ONT": "Ontario, CA",
    "SAN": "San Diego",
    "SNA": "Orange County",
    
    # Texas Cities
    "AUS": "Austin",
    "IAH": "Houston",
    "SAT": "San Antonio",
    
    # Florida
    "MCO": "Orlando",
    "MIA": "Miami",
    "FLL": "Fort Lauderdale",
    "TPA": "Tampa",
    
    # Other Major Cities
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
