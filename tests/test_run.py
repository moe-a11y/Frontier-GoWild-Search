#!/usr/bin/env python3
"""
Test script to run the flight scraper with predefined inputs
This demonstrates the new features:
- Date range selection (Dec 16-22, 2025)
- Specific destination airport (MIA - Miami)
"""

import sys
from io import StringIO
from unittest.mock import patch

# Mock user inputs
inputs = [
    "SFO",  # Origin airport
    "4",  # Date range option
    "2025-12-16",  # Start date
    "2025-12-22",  # End date
    "2",  # Specific destination
    "MIA",  # Miami airport code
]


def mock_input(prompt=""):
    """Mock input function to return predefined inputs"""
    if not inputs:
        return ""
    value = inputs.pop(0)
    print(prompt + value)
    return value


# Patch the input function
with patch("builtins.input", side_effect=mock_input):
    # Import and run the main function
    from gowild_scraper import main

    main()
